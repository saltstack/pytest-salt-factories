# -*- coding: utf-8 -*-
"""
saltfactories.utils.ports
~~~~~~~~~~~~~~~~~~~~~~~~~

Ports related utility functions
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging
import socket
import time

log = logging.getLogger(__name__)


def get_unused_localhost_port():
    """
    Return a random unused port on localhost
    """
    try:
        generated_ports = get_unused_localhost_port.__used_ports__
        # Cleanup ports. The idea behind this call is so that two consecutive calls to this
        # function don't return the same port just because the first call hasn't actuallt started
        # using the port.
        # It also makes this cache invalid after 1 second
        for port in list(generated_ports):
            if generated_ports[port] <= time.time():
                generated_ports.pop(port)
    except AttributeError:
        generated_ports = get_unused_localhost_port.__used_ports__ = {}

    usock = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
    usock.bind(("127.0.0.1", 0))
    port = usock.getsockname()[1]
    usock.close()
    if port not in generated_ports:
        generated_ports[port] = time.time() + 1
        return port
    return get_unused_localhost_port()


def check_connectable_ports(ports, timeout=30):
    ports = set(ports)
    expire = time.time() + timeout
    all_ports_connectable = True
    while True:
        if not ports:
            break
        if time.time() > expire:
            all_ports_connectable = False
            break

        for port in set(ports):
            log.debug("Checking connectable status on port: %s", port)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn = sock.connect_ex(("localhost", port))
            try:
                if conn == 0:
                    log.debug("Port %s is connectable!", port)
                    ports.remove(port)
                    sock.shutdown(socket.SHUT_RDWR)
            except socket.error:
                continue
            finally:
                sock.close()
                del sock
        time.sleep(0.5)
    return all_ports_connectable
