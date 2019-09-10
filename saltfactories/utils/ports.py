# -*- coding: utf-8 -*-
'''
saltfactories.utils.ports
~~~~~~~~~~~~~~~~~~~~~~~~~

Ports related utility functions
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import socket
import time


def get_unused_localhost_port():
    '''
    Return a random unused port on localhost
    '''
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
    usock.bind(('127.0.0.1', 0))
    port = usock.getsockname()[1]
    usock.close()
    if port not in generated_ports:
        generated_ports[port] = time.time() + 1
        return port
    return get_unused_localhost_port()
