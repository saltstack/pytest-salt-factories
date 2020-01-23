# -*- coding: utf-8 -*-
"""
pytestsalt.engines.pytest_engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Simple salt engine which will setup a socket to accept connections allowing us to know
when a daemon is up and running
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import errno
import logging
import os
import socket
import sys

import salt.utils.event
from tornado import gen
from tornado import ioloop
from tornado import iostream
from tornado import netutil


try:
    import salt.utils.asynchronous

    HAS_SALT_ASYNC = True
except ImportError:
    HAS_SALT_ASYNC = False


log = logging.getLogger(__name__)

__virtualname__ = "pytest"


def __virtual__():
    if "pytest" not in __opts__:
        return False, "No 'pytest' key in opts dictionary"
    if "engine" not in __opts__["pytest"]:
        return False, "No 'engine' key in 'pytest' opts dictionary"
    return True


def start():
    pytest_engine = PyTestEngine(__opts__)  # pylint: disable=undefined-variable
    pytest_engine.start()


class PyTestEngine(object):
    def __init__(self, opts):
        self.opts = opts
        self.id = opts["id"]
        self.role = opts["__role"]
        self.sock_dir = opts["sock_dir"]
        self.port = int(opts["pytest"]["engine"]["port"])
        self.tcp_server_sock = None
        self.stop_sending_events_file = opts["pytest"]["engine"]["stop_sending_events_file"]
        events = opts["pytest"]["engine"].get("events") or []
        # if not events:
        #    events.append('pytest/{}/{}/start'.format(self.role, self.id))
        self.events = events

    def start(self):
        self.io_loop = ioloop.IOLoop()
        self.io_loop.make_current()
        self.io_loop.add_callback(self._start)
        self.io_loop.start()

    @gen.coroutine
    def _start(self):
        log.info("Starting Pytest Engine(role=%s, id=%s) on port %s", self.role, self.id, self.port)

        self.tcp_server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_server_sock.setblocking(0)
        # bind the socket to localhost on the config provided port
        self.tcp_server_sock.bind(("localhost", self.port))
        # become a server socket
        self.tcp_server_sock.listen(5)
        if HAS_SALT_ASYNC:
            with salt.utils.asynchronous.current_ioloop(self.io_loop):
                netutil.add_accept_handler(self.tcp_server_sock, self.handle_connection)
        else:
            netutil.add_accept_handler(self.tcp_server_sock, self.handle_connection)

    def handle_connection(self, connection, address):
        log.warning(
            "Accepted connection from %s on %s. Role: %s  ID: %s",
            address,
            self.port,
            self.role,
            self.id,
        )
        if self.events:
            self.io_loop.add_callback(self.fire_started_event)
        # We just need to know that the daemon running the engine is alive...
        try:
            connection.shutdown(socket.SHUT_RDWR)  # pylint: disable=no-member
            connection.close()
        except socket.error as exc:
            if not sys.platform.startswith("darwin"):
                raise
            try:
                if exc.errno != errno.ENOTCONN:
                    raise
            except AttributeError:
                # This is not macOS !?
                pass

    @gen.coroutine
    def fire_started_event(self):
        log.warning("Starting to send started events for %s with ID %s", self.role, self.id)
        event_bus = salt.utils.event.get_master_event(self.opts, self.sock_dir, listen=False)
        # 30 seconds should be more than enough to fire these events every second in order
        # for pytest-salt to pickup that the master is running
        timeout = 30
        while True:
            if self.stop_sending_events_file and not os.path.exists(self.stop_sending_events_file):
                log.info('The stop sending events file "marker" is done. Stop sending events...')
                break
            timeout -= 1
            for event_tag in self.events:
                log.info("Firing started event. Tag: %s", event_tag)
                load = {"id": self.id, "tag": event_tag, "data": {}}
                try:
                    event_bus.fire_event(load, event_tag, timeout=500)
                except iostream.StreamClosedError:
                    break
            if timeout <= 0:
                break
            yield gen.sleep(1)
        event_bus.destroy()
