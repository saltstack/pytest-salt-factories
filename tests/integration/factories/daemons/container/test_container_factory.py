import pytest

from saltfactories.factories.daemons.container import ContainerFactory
from saltfactories.utils import ports
from saltfactories.utils import socket

docker = pytest.importorskip("docker")
from docker.errors import DockerException


@pytest.fixture(scope="module")
def docker_client():
    try:
        client = docker.from_env()
    except DockerException:
        pytest.skip("Failed to get a connection to docker running on the system")
    connectable = ContainerFactory.client_connectable(client)
    if connectable is not True:  # pragma: no cover
        pytest.skip(connectable)
    return client


@pytest.fixture(scope="module")
def echo_server_port():
    return ports.get_unused_localhost_port()


@pytest.fixture(scope="module")
def docker_container(salt_factories, docker_client, echo_server_port):
    container = salt_factories.get_container(
        "echo-server-test",
        "cjimti/go-echo",
        docker_client=docker_client,
        check_ports=[echo_server_port],
        container_run_kwargs={
            "ports": {"{}/tcp".format(echo_server_port): echo_server_port},
            "environment": {"TCP_PORT": str(echo_server_port), "NODE_NAME": "echo-server-test"},
        },
    )
    with container.started() as factory:
        yield factory


@pytest.mark.skip_on_darwin
@pytest.mark.skip_on_windows
def test_spawn_container(docker_container, echo_server_port):
    message = b"Hello!\n"
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect(("127.0.0.1", echo_server_port))
        client.settimeout(0.1)
        # Get any welcome message from the server
        while True:
            try:
                client.recv(4096)
            except socket.timeout:
                break
        client.send(message)
        response = None
        while True:
            try:
                response = client.recv(4096)
            except socket.timeout:
                break
        assert response is not None
        assert response == message
    finally:
        client.close()


@pytest.mark.skip_on_darwin
@pytest.mark.skip_on_windows
def test_container_run(docker_container):
    ret = docker_container.run("echo", "foo")
    assert ret.exitcode == 0
    assert ret.stdout == "foo\n"
    assert ret.stderr is None
    ret = docker_container.run("sh", "-c", ">&2 echo foo")
    assert ret.exitcode == 0
    assert ret.stdout is None
    assert ret.stderr == "foo\n"
