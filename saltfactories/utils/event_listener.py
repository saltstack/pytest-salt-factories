# -*- coding: utf-8 -*-
"""
saltfactories.utils.event_listener
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A "pseudo" event listener for salt factories pytest plugin
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import fnmatch
import logging
import threading
import time
from collections import deque

import msgpack
import zmq

from saltfactories.utils import ports

log = logging.getLogger(__name__)


class EventListener(object):
    def __init__(self, timeout=60):
        self.store = deque(maxlen=10000)
        self.address = "tcp://127.0.0.1:{}".format(ports.get_unused_localhost_port())
        self.timeout = timeout
        self.running_event = threading.Event()
        self.running_thread = threading.Thread(target=self._run)
        self.sentinel = msgpack.dumps(None)

    def _run(self):
        context = zmq.Context()
        puller = context.socket(zmq.PULL)
        puller.set_hwm(10000)
        log.debug("Binding PULL socket to %s", self.address)
        puller.bind(self.address)
        if msgpack.version >= (0, 5, 2):
            msgpack_kwargs = {"raw": False}
        else:
            msgpack_kwargs = {"encoding": "utf-8"}
        while self.running_event.is_set():
            payload = puller.recv()
            if payload is self.sentinel:
                break
            master_id, tag, data = msgpack.loads(payload, **msgpack_kwargs)
            received = time.time()
            expire = received + self.timeout
            log.info("Received event from: MasterID: %r; Tag: %r; Data: %r", master_id, tag, data)
            self.store.append((received, expire, master_id, tag, data))

            # Cleanup expired events
            to_remove = []
            for received, expire, master_id, tag, data in self.store:
                if time.time() > expire:
                    to_remove.append((received, expire, master_id, tag, data))

            for entry in to_remove:
                self.store.remove(entry)

    def start(self):
        if self.running_event.is_set():
            return
        self.running_event.set()
        self.running_thread.start()

    def stop(self):
        if self.running_event.is_set() is False:
            return
        self.running_event.clear()
        context = zmq.Context()
        push = context.socket(zmq.PUSH)
        push.connect(self.address)
        push.send(self.sentinel)
        push.close(1500)
        context.term()

    def wait_for_events(self, patterns, timeout=30, after_time=None):
        start_time = time.time()
        patterns = set(patterns)
        log.info("Waiting at most %.2f seconds for event patterns: %s", timeout, patterns)
        if after_time is None:
            after_time = time.time()
        expire = start_time + timeout
        while time.time() <= expire:
            if not patterns:
                break

            for received, expire, master_id, tag, data in self.store:
                if received < after_time:
                    # Too old, carry on
                    continue
                for _master_id, _pattern in set(patterns):
                    if _master_id != master_id:
                        continue
                    if fnmatch.fnmatch(tag, _pattern):
                        patterns.remove((_master_id, _pattern))
            time.sleep(0.125)
        else:
            log.info(
                "Timmed out after %.2f seconds waiting for event patterns: %s",
                time.time() - start_time,
                patterns,
            )
            return False
        return True
