import pytest

from saltfactories.daemons.container import Container

docker = pytest.importorskip("docker")
from docker.errors import DockerException  # noqa: E402


@pytest.fixture(scope="session")
def docker_client():
    try:
        client = docker.from_env()
    except DockerException:
        pytest.skip("Failed to get a connection to docker running on the system")
    connectable = Container.client_connectable(client)
    if connectable is not True:  # pragma: no cover
        pytest.skip(connectable)
    return client
