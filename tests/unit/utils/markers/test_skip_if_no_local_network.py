"""
    tests.unit.utils.markers.test_skip_if_no_local_network
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the "skip_if_no_local_network" marker helper
"""
from unittest import mock

import saltfactories.utils.markers as markers
from saltfactories.utils import ports
from saltfactories.utils import socket


def test_has_local_network():
    assert markers.skip_if_no_local_network() is None


def test_no_local_network():
    mock_socket = mock.MagicMock()
    mock_socket.bind = mock.MagicMock(side_effect=socket.error)
    with mock.patch(
        "saltfactories.utils.ports.get_unused_localhost_port",
        side_effect=[ports.get_unused_localhost_port() for n in range(10)],
    ):
        with mock.patch("saltfactories.utils.markers.socket.socket", return_value=mock_socket):
            skip_reason = markers.skip_if_no_local_network()
            assert skip_reason is not None
            assert skip_reason == "No local network was detected"
