"""
saltfactories.utils.ports
~~~~~~~~~~~~~~~~~~~~~~~~~

Ports related utility functions
"""
import contextlib
import logging
import socket
import time

log = logging.getLogger(__name__)


def get_unused_localhost_port(cached_seconds=10):
    """
    Return a random unused port on localhost
    """
    if not isinstance(cached_seconds, (int, float)):
        raise RuntimeError(
            "The value of 'cached_seconds' needs to be an integer or a float, not {}".format(
                type(cached_seconds)
            )
        )
    if cached_seconds < 0:
        raise RuntimeError(
            "The value of 'cached_seconds' needs to be a positive number, not {}".format(
                cached_seconds
            )
        )
    try:
        generated_ports = get_unused_localhost_port.__used_ports__
        # Cleanup ports. The idea behind this call is so that two consecutive calls to this
        # function don't return the same port just because the first call hasn't actually started
        # using the port.
        # It also makes this cache invalid after <cached_seconds> second
        for port in list(generated_ports):
            if generated_ports[port] <= time.time():
                generated_ports.pop(port)
    except AttributeError:
        generated_ports = get_unused_localhost_port.__used_ports__ = {}

    with contextlib.closing(socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)) as usock:
        usock.bind(("127.0.0.1", 0))
        port = usock.getsockname()[1]
    if port not in generated_ports:
        generated_ports[port] = time.time() + cached_seconds
        return port
    return get_unused_localhost_port(cached_seconds=cached_seconds)


def get_connectable_ports(ports):
    connectable_ports = set()
    ports = set(ports)

    for port in set(ports):
        with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            conn = sock.connect_ex(("localhost", port))
            try:
                if conn == 0:
                    log.debug("Port %s is connectable!", port)
                    connectable_ports.add(port)
                    sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                continue
    return connectable_ports
