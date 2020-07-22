import socket

import pytest

from saltfactories.utils import ports

pytest.importorskip("docker")


@pytest.fixture(scope="module")
def echo_server_port():
    return ports.get_unused_localhost_port()


@pytest.mark.skip_if_binaries_missing("docker", reason="Docker does not appear to be installed")
def test_spawn_docker_container(request, salt_factories, echo_server_port):
    factory = salt_factories.spawn_docker_container(
        request,
        "echo-server-test",
        "cjimti/go-echo",
        container_run_kwargs={
            "ports": {"{}/tcp".format(echo_server_port): echo_server_port},
            "environment": {"TCP_PORT": str(echo_server_port), "NODE_NAME": "echo-server-test"},
        },
    )
    message = b"Hello!\n"
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect(("127.0.0.1", echo_server_port))
        client.settimeout(0.1)
        # Get any welcome message from the server
        while True:
            try:
                data = client.recv(4096)
            except socket.timeout:
                break
        client.send(message)
        while True:
            try:
                response = client.recv(4096)
            except socket.timeout:
                break
        assert response == message
    finally:
        client.close()
