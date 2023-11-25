import logging

import pytest

from saltfactories.daemons.container import SaltMaster
from saltfactories.daemons.container import SaltMinion
from saltfactories.utils import random_string

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)


pytestmark = [
    # We can't pass ``extra_cli_arguments_after_first_start_failure``, but this is solvable,
    # but we also rely on container volume binds, which, when running against the system,
    # means trying to bind `/`, which is not possible, hence, we're skipping this test.
    pytest.mark.skip_on_salt_system_service,
    pytest.mark.skip_on_darwin,
    pytest.mark.skip_on_windows,
]


@pytest.fixture(scope="session")
def docker_client(salt_factories, docker_client):
    if salt_factories.system_service:  # pragma: no cover
        msg = "Test should not run against system install of Salt"
        raise pytest.skip.Exception(msg, _use_item_location=True)
    return docker_client


@pytest.fixture(scope="module")
def minion_id(salt_version):
    return random_string(f"salt-minion-{salt_version}-", uppercase=False)


@pytest.fixture(scope="module")
def master_id(salt_version):
    return random_string(f"salt-master-{salt_version}-", uppercase=False)


@pytest.fixture(scope="module")
def salt_master(
    salt_factories, docker_client, docker_network_name, master_id, host_docker_network_ip_address
):
    config_overrides = {
        "open_mode": True,
        "user": "root",
        "interface": "0.0.0.0",  # noqa: S104
        "log_level_logfile": "quiet",
        "pytest-master": {
            "log": {"host": host_docker_network_ip_address},
            "returner_address": {"host": host_docker_network_ip_address},
        },
    }

    factory = salt_factories.salt_master_daemon(
        master_id,
        name=master_id,
        overrides=config_overrides,
        factory_class=SaltMaster,
        base_script_args=["--log-level=debug"],
        image="ghcr.io/saltstack/salt-ci-containers/salt:3006",
        container_run_kwargs={
            "network": docker_network_name,
            "hostname": master_id,
        },
        docker_client=docker_client,
        start_timeout=660,
        max_start_attempts=1,
        pull_before_start=True,
    )

    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def salt_minion(
    minion_id,
    salt_master,
    docker_client,
    docker_network_name,
    host_docker_network_ip_address,
):
    config_overrides = {
        "master": salt_master.id,
        "user": "root",
        "pytest-minion": {
            "log": {"host": host_docker_network_ip_address},
            "returner_address": {"host": host_docker_network_ip_address},
        },
        "open_mode": True,
    }
    factory = salt_master.salt_minion_daemon(
        minion_id,
        overrides=config_overrides,
        factory_class=SaltMinion,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
        # SaltMinion kwargs
        name=minion_id,
        image="ghcr.io/saltstack/salt-ci-containers/salt:3006",
        container_run_kwargs={
            "network": docker_network_name,
            "hostname": minion_id,
        },
        docker_client=docker_client,
        start_timeout=60,
        max_start_attempts=1,
        pull_before_start=True,
    )
    with factory.started():
        yield factory


@pytest.fixture
def salt_cli(salt_master, salt_cli_timeout):
    return salt_master.salt_cli(timeout=salt_cli_timeout)


def test_master(salt_minion, salt_master, salt_cli):
    # If the minion is running, and we can ping it, so is the master in the container
    assert salt_minion.is_running()

    ret = salt_master.run(
        *salt_cli.cmdline(
            "test.ping",
            minion_tgt=salt_minion.id,
        )
    )
    assert ret.returncode == 0
    assert ret.data
    assert salt_minion.id in ret.data
    assert ret.data[salt_minion.id] is True
