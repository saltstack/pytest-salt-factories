"""
saltfactories.plugins.event_listener
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A "pseudo" event listener for salt factories pytest plugin
"""
import copy
import fnmatch
import logging
import threading
import weakref
from collections import deque
from datetime import datetime

import attr
import msgpack
import pytest
import zmq

from saltfactories.utils import ports
from saltfactories.utils import time

log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True, hash=True)
class EventListener:
    timeout = attr.ib(default=120)
    address = attr.ib(init=False)
    store = attr.ib(init=False, repr=False, hash=False)
    sentinel = attr.ib(init=False, repr=False, hash=False)
    running_event = attr.ib(init=False, repr=False, hash=False)
    running_thread = attr.ib(init=False, repr=False, hash=False)
    cleaning_thread = attr.ib(init=False, repr=False, hash=False)
    auth_event_handlers = attr.ib(init=False, repr=False, hash=False)

    def __attrs_post_init__(self):
        self.store = deque(maxlen=10000)
        self.address = "tcp://127.0.0.1:{}".format(ports.get_unused_localhost_port())
        self.running_event = threading.Event()
        self.running_thread = threading.Thread(target=self._run)
        self.cleaning_thread = threading.Thread(target=self._cleanup)
        self.cleaning_thread.daemon = True
        self.sentinel = msgpack.dumps(None)
        self.auth_event_handlers = weakref.WeakValueDictionary()

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
                log.info("Received stop sentinel...")
                break
            master_id, tag, data = msgpack.loads(payload, **msgpack_kwargs)
            received = time.time()
            expire = received + self.timeout
            log.info("Received event from: MasterID: %r; Tag: %r; Data: %r", master_id, tag, data)
            self.store.append((received, expire, master_id, tag, data))
            if tag == "salt/auth":
                auth_event_callback = self.auth_event_handlers.get(master_id)
                if auth_event_callback:
                    auth_event_callback(data)

    def _cleanup(self):
        cleanup_at = time.time() + 30
        while self.running_event.is_set():
            if time.time() < cleanup_at:
                time.sleep(1)
                continue

            # Reset cleanup time
            cleanup_at = time.time() + 30

            # Cleanup expired events
            to_remove = []
            for received, expire, master_id, tag, data in self.store:
                if time.time() > expire:
                    to_remove.append((received, expire, master_id, tag, data))

            for entry in to_remove:
                log.debug("Removing from event store: %s", entry)
                self.store.remove(entry)
            log.debug("Event store size: %s", len(self.store))

    def start(self):
        if self.running_event.is_set():
            return
        self.running_event.set()
        self.running_thread.start()
        self.cleaning_thread.start()

    def stop(self):
        if self.running_event.is_set() is False:
            return
        self.store.clear()
        self.running_event.clear()
        context = zmq.Context()
        push = context.socket(zmq.PUSH)
        push.connect(self.address)
        push.send(self.sentinel)
        push.close(1500)
        context.term()
        self.running_thread.join()

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

            for received, expire, master_id, tag, data in copy.copy(self.store):
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

    def get_events(self, patterns, after_time=None):
        after_time_iso = datetime.fromtimestamp(after_time).isoformat()
        log.debug(
            "%s is checking for event patterns happening after %s: %s",
            self,
            after_time_iso,
            set(patterns),
        )
        found_patterns = set()
        patterns = set(patterns)
        if after_time is None:
            after_time = time.time()
        for received, expire, master_id, tag, data in copy.copy(self.store):
            if received < after_time:
                # Too old, carry on
                continue
            for pattern in set(patterns):
                _master_id, _pattern = pattern
                if _master_id != master_id:
                    continue
                if fnmatch.fnmatch(tag, _pattern):
                    log.debug("Found matching pattern: %s", pattern)
                    found_patterns.add(pattern)
        if found_patterns:
            log.debug(
                "%s found the following patterns happening after %s: %s",
                self,
                after_time_iso,
                found_patterns,
            )
        else:
            log.debug(
                "%s did not find any matching event patterns happening after %s",
                self,
                after_time_iso,
            )
        return found_patterns

    def register_auth_event_handler(self, master_id, callback):
        self.auth_event_handlers[master_id] = callback

    def unregister_auth_event_handler(self, master_id):
        self.auth_event_handlers.pop(master_id, None)


def pytest_configure(config):
    event_listener = EventListener()
    config.pluginmanager.register(event_listener, "saltfactories-event-listener")


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    event_listener = session.config.pluginmanager.get_plugin("saltfactories-event-listener")
    event_listener.start()


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session):
    event_listener = session.config.pluginmanager.get_plugin("saltfactories-event-listener")
    event_listener.stop()
