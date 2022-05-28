import io
import logging

import _pytest._version
import pytest
import salt.version

from saltfactories.daemons.container import SaltMinion
from saltfactories.utils import random_string

docker = pytest.importorskip("docker")
import docker.types  # noqa: E402
from docker.errors import DockerException  # noqa: E402

log = logging.getLogger(__name__)

PYTEST_GE_7 = getattr(_pytest._version, "version_tuple", (-1, -1)) >= (7, 0)

pytestmark = [
    # We can't pass ``extra_cli_arguments_after_first_start_failure``, but this is solvable,
    # but we also rely on container volume binds, which, when running against the system,
    # means trying to bind `/`, which is not possible, hence, we're skipping this test.
    pytest.mark.skip_on_salt_system_install,
    pytest.mark.skip_on_darwin,
    pytest.mark.skip_on_windows,
]


DOCKERFILE = """
FROM {from_container}
ENV LANG=en_US.UTF8

ENV VIRTUAL_ENV={virtualenv_path}

RUN virtualenv --python=python3 $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN pip install {requirements}

CMD . $VIRTUAL_ENV/bin/activate
"""


@pytest.fixture(scope="session")
def docker_client(salt_factories, docker_client):
    if salt_factories.system_install:
        exc_kwargs = {}
        if PYTEST_GE_7:
            exc_kwargs["_use_item_location"] = True
        raise pytest.skip.Exception(
            "Test should not run against system install of Salt", **exc_kwargs
        )
    return docker_client


@pytest.fixture(scope="session")
def host_docker_network_ip_address(docker_client):
    network_name = "salt-factories-e2e"
    network_subnet = "10.0.21.0/24"
    network_gateway = "10.0.21.1"
    network = None
    try:
        network = docker_client.api.inspect_network(network_name)
        yield network_gateway
    except DockerException:
        ipam_pool = docker.types.IPAMPool(
            subnet=network_subnet,
            gateway=network_gateway,
        )
        ipam_config = docker.types.IPAMConfig(pool_configs=[ipam_pool])
        network = docker_client.networks.create(
            network_name,
            driver="bridge",
            ipam=ipam_config,
        )
        yield network_gateway
    finally:
        if network is not None:
            docker_client.networks.prune()


@pytest.fixture(scope="session")
def salt_factories_config(salt_factories_config, host_docker_network_ip_address):
    """
    Return a dictionary with the keyword arguments for FactoriesManager
    """
    config = salt_factories_config.copy()
    config["log_server_host"] = host_docker_network_ip_address
    return config


@pytest.fixture(scope="module")
def container_virtualenv_path():
    return "/tmp/venv"


@pytest.fixture(scope="module")
def minion_image_name(salt_version):
    return "salt-{}".format(salt_version)


@pytest.fixture(scope="module")
def minion_image(docker_client, salt_version, container_virtualenv_path, minion_image_name):
    salt_versions_information = salt.version.versions_information()
    requirements = ""
    for name in ("PyZMQ", "Jinja2", "PyYAML"):
        version = salt_versions_information["Dependency Versions"].get(name)
        if version:
            requirements += " {}=={}".format(name.lower(), version)
    requirements += " salt=={}".format(salt_version)
    dockerfile_contents = DOCKERFILE.format(
        from_container="saltstack/ci-centos-7",
        requirements=requirements.strip(),
        virtualenv_path=container_virtualenv_path,
    )
    log.debug("GENERATED Dockerfile:\n%s", dockerfile_contents)
    dockerfile_fh = io.BytesIO(dockerfile_contents.encode("utf-8"))
    _, logs = docker_client.images.build(
        fileobj=dockerfile_fh,
        tag=minion_image_name,
        pull=True,
    )
    return minion_image_name


@pytest.fixture(scope="function")
def minion_id(salt_version):
    return random_string(
        "salt-{}-".format(salt_version),
        uppercase=False,
    )


@pytest.fixture(scope="module")
def salt_master(salt_factories, minion_image, host_docker_network_ip_address):
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
    minion_image,
    host_docker_network_ip_address,
):
    config_overrides = {
        "master": salt_master.config["interface"],
        "user": False,
        "pytest-minion": {"log": {"host": host_docker_network_ip_address}},
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
        image=minion_image,
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
