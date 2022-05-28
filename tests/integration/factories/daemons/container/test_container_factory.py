import logging

import pytest
from pytestshellutils.exceptions import FactoryNotStarted
from pytestshellutils.utils import ports
from pytestshellutils.utils import socket

pytestmark = [
    pytest.mark.skip_on_darwin,
    pytest.mark.skip_on_windows,
]


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
    assert ret.returncode == 0
    assert ret.stdout == "foo\n"
    assert ret.stderr is None
    ret = docker_container.run("sh", "-c", ">&2 echo foo")
    assert ret.returncode == 0
    assert ret.stdout is None
    assert ret.stderr == "foo\n"


@pytest.fixture(scope="module")
def docker_container_random_port(salt_factories, docker_client):
    container = salt_factories.get_container(
        "echo-server-test-random-port",
        "cjimti/go-echo",
        docker_client=docker_client,
        container_run_kwargs={
            "ports": {"5000/tcp": None},
            "environment": {"TCP_PORT": "5000", "NODE_NAME": "echo-server-test-random-port"},
        },
    )
    with container.started() as factory:
        yield factory


def test_container_random_host_port(docker_container_random_port, echo_server_port):
    message = b"Hello!\n"
    echo_server_port = docker_container_random_port.get_host_port_binding(5000, protocol="tcp")
    assert echo_server_port is not None
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


def test_non_connectable_check_ports(salt_factories, docker_client, caplog):
    container = salt_factories.get_container(
        "echo-server-test-fail",
        "cjimti/go-echo",
        docker_client=docker_client,
        check_ports={12345: 12345},
        container_run_kwargs={
            "ports": {"5000/tcp": None},
            "environment": {"TCP_PORT": "5000", "NODE_NAME": "echo-server-test"},
        },
        start_timeout=3,
        max_start_attempts=1,
    )
    assert set(container.check_ports.items()) == {(5000, None), (12345, 12345)}
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(FactoryNotStarted):
            container.start()
    assert "Remaining ports to check: {12345: 12345}" in caplog.text
