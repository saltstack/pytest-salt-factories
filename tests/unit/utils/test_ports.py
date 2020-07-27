"""
tests.utils.test_ports
~~~~~~~~~~~~~~~~~~~~~~

Test the port related utilities
"""
import functools
import time
from unittest import mock

import pytest

import saltfactories.utils.ports as ports_utils


class MockedCreateSocket:
    """
    This class just mocks the `socket.socket(...)` call so that we return
    the ports we want
    """

    def __init__(self, ports):
        self.ports = list(ports) + list(ports)

    def __call__(self, *args, **kwargs):
        port = self.ports.pop(0)
        # Return a MockedSocket instance
        return MockedSocket(port)


class MockedSocket:
    """
    This class is used so that we can return the known port in the getsockname call
    """

    def __init__(self, port):
        self.port = port

    def bind(self, *args, **kwargs):
        pass

    def getsockname(self):
        return None, self.port

    def close(self):
        pass


def test_get_unused_localhost_port_unique():
    """
    Tests that test_get_unused_localhost_port only returns unique ports on consecutive calls
    """
    num_calls = 10
    start_port = 1000
    # The ports we're gonna get back
    ports = []
    for port in range(start_port, start_port + num_calls):
        for _ in range(num_calls):
            # We make sure each port is repeated consecutively
            ports.append(port)

    # Hold a reference to the list of unique ports
    unique = set(ports)

    # This list will hold all ports that the function returns
    got_ports = []

    # We'll get the unique ports
    with mock.patch(
        "socket.socket", new_callable=functools.partial(MockedCreateSocket, ports)
    ) as mocked_socket:
        for _ in range(num_calls):
            got_ports.append(ports_utils.get_unused_localhost_port(cached_seconds=1))
        assert len(got_ports) == num_calls
        assert set(got_ports) == unique

    # Let's get ports again. Since not enough time has passed, we won't get any ports
    with mock.patch(
        "socket.socket", new_callable=functools.partial(MockedCreateSocket, ports + ports)
    ) as mocked_socket:
        for _ in range(num_calls):
            with pytest.raises(IndexError):
                # we won't have enough ports
                got_ports.append(ports_utils.get_unused_localhost_port(cached_seconds=1))
        # Since we couldn't get repeated ports, got_ports remains as it was
        assert len(got_ports) == num_calls
        assert set(got_ports) == unique

    # Now, if we sleep one second, the cached ports will be gone and we'll get repeated ports
    time.sleep(1)
    with mock.patch(
        "socket.socket", new_callable=functools.partial(MockedCreateSocket, ports)
    ) as mocked_socket:
        for _ in range(num_calls):
            got_ports.append(ports_utils.get_unused_localhost_port(cached_seconds=1))

        assert len(got_ports) == 2 * len(unique)
        assert set(got_ports) == unique
