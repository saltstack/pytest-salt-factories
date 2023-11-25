import attr
import pytest

from saltfactories.daemons.container import Container

docker = pytest.importorskip("docker")
from docker.errors import DockerException  # noqa: E402


@pytest.fixture(scope="session")
def docker_client():
    try:
        client = docker.from_env()
    except DockerException:  # pragma: no cover
        pytest.skip("Failed to get a connection to docker running on the system")
    connectable = Container.client_connectable(client)
    if connectable is not True:  # pragma: no cover
        pytest.skip(connectable)
    return client


@pytest.fixture(scope="session")
def docker_network_name():
    return "salt-factories-e2e"


@pytest.fixture(scope="session")
def host_docker_network_ip_address(docker_client, docker_network_name):
    network_subnet = "10.0.21.0/24"
    network_gateway = "10.0.21.1"
    network = None
    try:
        network = docker_client.api.inspect_network(docker_network_name)
        yield network_gateway
    except DockerException:
        ipam_pool = docker.types.IPAMPool(
            subnet=network_subnet,
            gateway=network_gateway,
        )
        ipam_config = docker.types.IPAMConfig(pool_configs=[ipam_pool])
        network = docker_client.networks.create(
            docker_network_name,
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
    Return a dictionary with the keyword arguments for FactoriesManager.
    """
    config = salt_factories_config.copy()
    config["log_server_host"] = host_docker_network_ip_address
    return config


@attr.s(slots=True)
class ContainerCallbacksCounter:
    """
    A callbacks counter.
    """

    before_start_count = attr.ib(init=False, default=0)
    after_start_count = attr.ib(init=False, default=0)
    before_terminate_count = attr.ib(init=False, default=0)
    after_terminate_count = attr.ib(init=False, default=0)

    def before_start(self):
        self.before_start_count += 1

    def after_start(self):
        self.after_start_count += 1

    def before_terminate(self):
        self.before_terminate_count += 1

    def after_terminate(self):
        self.after_terminate_count += 1


@attr.s(slots=True)
class SaltCallbacksCounter(ContainerCallbacksCounter):
    """
    The same, thing, a different class name.
    """
