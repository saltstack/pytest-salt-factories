import logging

import pytest

from saltfactories.daemons.container import SaltMinion
from saltfactories.utils import random_string

from .conftest import ContainerCallbacksCounter
from .conftest import SaltCallbacksCounter

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


@pytest.fixture
def minion_id(salt_version):
    return random_string(f"salt-minion-{salt_version}-", uppercase=False)


@pytest.fixture(scope="module")
def salt_master(salt_factories, host_docker_network_ip_address):
    config_overrides = {
        "interface": host_docker_network_ip_address,
        "log_level_logfile": "quiet",
        # We also want to scrutinize the key acceptance
        "open_mode": True,
    }
    factory = salt_factories.salt_master_daemon(
        random_string("master-"),
        overrides=config_overrides,
    )
    with factory.started():
        yield factory


@pytest.fixture
def salt_minion(
    minion_id,
    salt_master,
    docker_client,
    host_docker_network_ip_address,
):
    config_overrides = {
        "master": salt_master.config["interface"],
        "user": "root",
        "pytest-minion": {
            "log": {"host": host_docker_network_ip_address},
            "returner_address": {"host": host_docker_network_ip_address},
        },
        # We also want to scrutinize the key acceptance
        "open_mode": False,
    }
    factory = salt_master.salt_minion_daemon(
        minion_id,
        overrides=config_overrides,
        factory_class=SaltMinion,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
        # SaltMinion kwargs
        name=minion_id,
        image="ghcr.io/saltstack/salt-ci-containers/salt:3006",
        docker_client=docker_client,
        start_timeout=120,
        pull_before_start=False,
    )
    with factory.started():
        yield factory


@pytest.fixture
def salt_cli(salt_master, salt_cli_timeout):
    return salt_master.salt_cli(timeout=salt_cli_timeout)


def test_minion(salt_minion, salt_cli):
    assert salt_minion.is_running()
    ret = salt_cli.run("test.ping", minion_tgt=salt_minion.id)
    assert ret.returncode == 0, ret
    assert ret.data is True


def test_callbacks(salt_master, docker_client, host_docker_network_ip_address):
    minion_id = random_string("salt-cb-counter-", uppercase=False)
    salt_counter = SaltCallbacksCounter()
    container_counter = ContainerCallbacksCounter()

    config_overrides = {
        "master": salt_master.config["interface"],
        "user": False,
        "pytest-minion": {
            "log": {"host": host_docker_network_ip_address},
            "returner_address": {"host": host_docker_network_ip_address},
        },
        # We also want to scrutinize the key acceptance
        "open_mode": False,
    }
    container = salt_master.salt_minion_daemon(
        minion_id,
        overrides=config_overrides,
        factory_class=SaltMinion,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
        # SaltMinion kwargs
        name=minion_id,
        image="ghcr.io/saltstack/salt-ci-containers/salt:3006",
        docker_client=docker_client,
        start_timeout=120,
        pull_before_start=True,
    )

    for callback in container._before_start_callbacks:
        if callback.func == container._pull_container:
            break
    else:
        pytest.fail("Failed to find the container._pull_container callback")

    container.before_start(container_counter.before_start, on_container=True)
    container.after_start(container_counter.after_start, on_container=True)
    container.before_terminate(container_counter.before_terminate, on_container=True)
    container.after_terminate(container_counter.after_terminate, on_container=True)

    container.before_start(salt_counter.before_start)
    container.after_start(salt_counter.after_start)
    container.before_terminate(salt_counter.before_terminate)
    container.after_terminate(salt_counter.after_terminate)

    assert container_counter.before_start_count == 0
    assert container_counter.after_start_count == 0
    assert container_counter.before_terminate_count == 0
    assert container_counter.after_terminate_count == 0

    assert salt_counter.before_start_count == 0
    assert salt_counter.after_start_count == 0
    assert salt_counter.before_terminate_count == 0
    assert salt_counter.after_terminate_count == 0

    with container.started():
        assert container_counter.before_start_count == 1
        assert container_counter.after_start_count == 1
        assert container_counter.before_terminate_count == 0
        assert container_counter.after_terminate_count == 0

        assert salt_counter.before_start_count == 1
        assert salt_counter.after_start_count == 1
        assert salt_counter.before_terminate_count == 0
        assert salt_counter.after_terminate_count == 0

    assert container_counter.before_start_count == 1
    assert container_counter.after_start_count == 1
    assert container_counter.before_terminate_count == 1
    assert container_counter.after_terminate_count == 1

    assert salt_counter.before_start_count == 1
    assert salt_counter.after_start_count == 1
    assert salt_counter.before_terminate_count == 1
    assert salt_counter.after_terminate_count == 1
