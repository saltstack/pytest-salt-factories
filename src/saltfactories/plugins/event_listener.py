"""
Salt Factories Event Listener.

A salt events store for all daemons started by salt-factories
"""
import copy
import fnmatch
import logging
import threading
import weakref
from collections import deque
from datetime import datetime
from datetime import timedelta

import attr
import msgpack
import pytest
import zmq
from pytestshellutils.utils import ports
from pytestshellutils.utils import time


log = logging.getLogger(__name__)


def _convert_stamp(stamp):
    try:
        return datetime.fromisoformat(stamp)
    except AttributeError:  # pragma: no cover
        # Python < 3.7
        return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S.%f")


@attr.s(kw_only=True, slots=True, hash=True, frozen=True)
class Event:
    """
    Event wrapper class.

    The ``Event`` class is a container for a salt event which will live on the
    :py:class:`~saltfactories.plugins.event_listener.EventListener` store.

    :keyword str daemon_id:
        The daemon ID which received this event.
    :keyword str tag:
        The event tag of the event.
    :keyword ~datetime.datetime stamp:
        When the event occurred
    :keyword dict data:
        The event payload, filtered of all of Salt's private keys like ``_stamp`` which prevents proper
        assertions against it.
    :keyword dict full_data:
        The full event payload, as received by the daemon, including all of Salt's private keys.
    :keyword int,float expire_seconds:
        The time, in seconds, after which the event should be considered as expired and removed from the store.
    """

    daemon_id = attr.ib()
    tag = attr.ib()
    stamp = attr.ib(converter=_convert_stamp)
    data = attr.ib(hash=False)
    full_data = attr.ib(hash=False)
    expire_seconds = attr.ib(hash=False)
    _expire_at = attr.ib(init=False, hash=False)

    @_expire_at.default
    def _set_expire_at(self):
        return self.stamp + timedelta(seconds=self.expire_seconds)

    @property
    def expired(self):
        """
        Property to identify if the event has expired, at which time it should be removed from the store.
        """
        if datetime.utcnow() < self._expire_at:
            return False
        return True


@attr.s(kw_only=True, slots=True, hash=True, frozen=True)
class MatchedEvents:
    """
    MatchedEvents implementation.

    The ``MatchedEvents`` class is a container which is returned by
    :py:func:`~saltfactories.plugins.event_listener.EventListener.wait_for_events`.

    :keyword set matches:
        A :py:class:`set` of :py:class:`~saltfactories.plugins.event_listener.Event` instances that matched.
    :keyword set missed:
        A :py:class:`set` of :py:class:`~saltfactories.plugins.event_listener.Event` instances that remained
        unmatched.

    One can also easily iterate through all matched events of this class:

    .. code-block:: python

        matched_events = MatchedEvents(..., ...)
        for event in matched_events:
            print(event.tag)
    """

    matches = attr.ib()
    missed = attr.ib()

    @property
    def found_all_events(self):
        """
        :return bool: :py:class:`True` if all events were matched, or :py:class:`False` otherwise.
        """
        return (not self.missed) is True

    def __iter__(self):
        """
        Iterate through the matched events.
        """
        return iter(self.matches)


@attr.s(kw_only=True, slots=True, hash=True)
class EventListener:
    """
    EventListener implementation.

    The ``EventListener`` is a service started by salt-factories which receives all the events of all the
    salt masters that it starts. The service runs throughout the whole pytest session.

    :keyword int timeout:
        How long, in seconds, should a forwarded event stay in the store, after which, it will be deleted.
    """

    timeout = attr.ib(default=120)
    address = attr.ib(init=False)
    store = attr.ib(init=False, repr=False, hash=False)
    sentinel = attr.ib(init=False, repr=False, hash=False)
    sentinel_event = attr.ib(init=False, repr=False, hash=False)
    running_event = attr.ib(init=False, repr=False, hash=False)
    running_thread = attr.ib(init=False, repr=False, hash=False)
    cleanup_thread = attr.ib(init=False, repr=False, hash=False)
    auth_event_handlers = attr.ib(init=False, repr=False, hash=False)

    def __attrs_post_init__(self):
        """
        Post attrs initialization routines.
        """
        self.store = deque(maxlen=10000)
        self.address = "tcp://127.0.0.1:{}".format(ports.get_unused_localhost_port())
        self.running_event = threading.Event()
        self.running_thread = threading.Thread(target=self._run)
        self.cleanup_thread = threading.Thread(target=self._cleanup)
        self.sentinel = msgpack.dumps(None)
        self.sentinel_event = threading.Event()
        self.auth_event_handlers = weakref.WeakValueDictionary()

    def _run(self):
        context = zmq.Context()
        puller = context.socket(zmq.PULL)  # pylint: disable=no-member
        log.debug("%s Binding PULL socket to %s", self, self.address)
        puller.bind(self.address)
        if msgpack.version >= (0, 5, 2):
            msgpack_kwargs = {"raw": False}
        else:  # pragma: no cover
            msgpack_kwargs = {"encoding": "utf-8"}
        log.debug("%s started", self)
        self.running_event.set()
        while self.running_event.is_set():
            payload = puller.recv()
            if payload == self.sentinel:
                log.info("%s Received stop sentinel...", self)
                self.sentinel_event.set()
                break
            try:
                decoded = msgpack.loads(payload, **msgpack_kwargs)
            except ValueError:  # pragma: no cover
                log.error(
                    "%s Failed to msgpack.load message with payload: %s",
                    self,
                    payload,
                    exc_info=True,
                )
                continue
            if decoded is None:
                log.info("%s Received stop sentinel...", self)
                self.sentinel_event.set()
                break
            try:
                daemon_id, tag, data = decoded
                # Salt's event data has some "private" keys, for example, "_stamp" which
                # get in the way of direct assertions.
                # We'll just store a full_data attribute and clean up the regular data of these keys
                full_data = copy.deepcopy(data)
                for key in list(data):
                    if key.startswith("_"):
                        data.pop(key)
                event = Event(
                    daemon_id=daemon_id,
                    tag=tag,
                    stamp=full_data["_stamp"],
                    data=data,
                    full_data=full_data,
                    expire_seconds=self.timeout,
                )
                log.info("%s received event: %s", self, event)
                self.store.append(event)
                if tag == "salt/auth":
                    auth_event_callback = self.auth_event_handlers.get(daemon_id)
                    if auth_event_callback:
                        try:
                            auth_event_callback(data)
                        except Exception as exc:  # pragma: no cover pylint: disable=broad-except
                            log.error(
                                "%s Error calling %r: %s",
                                self,
                                auth_event_callback,
                                exc,
                                exc_info=True,
                            )
                log.debug("%s store size after event received: %d", self, len(self.store))
            except Exception:  # pragma: no cover pylint: disable=broad-except
                log.error("%s Something funky happened", self, exc_info=True)
                puller.close(0)
                context.term()
                # We need to keep these events stored, restart zmq socket
                context = zmq.Context()
                puller = context.socket(zmq.PULL)  # pylint: disable=no-member
                log.debug("%s Binding PULL socket to %s", self, self.address)
                puller.bind(self.address)
        puller.close(1500)
        context.term()
        log.debug("%s is no longer running", self)

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
            for event in self.store:
                if event.expired:
                    to_remove.append(event)

            for event in to_remove:
                log.debug("%s Removing from event store: %s", self, event)
                self.store.remove(event)
            log.debug("%s store size after cleanup: %s", self, len(self.store))

    def start(self):
        """
        Start the event listener.
        """
        if self.running_event.is_set():  # pragma: no cover
            return
        log.debug("%s is starting", self)
        self.running_thread.start()
        # Wait for the thread to start
        if self.running_event.wait(5) is not True:
            self.running_event.clear()
            raise RuntimeError("Failed to start the event listener")
        self.cleanup_thread.start()

    def stop(self):
        """
        Stop the event listener.
        """
        if self.running_event.is_set() is False:  # pragma: no cover
            return
        log.debug("%s is stopping", self)
        self.store.clear()
        self.auth_event_handlers.clear()
        context = zmq.Context()
        push = context.socket(zmq.PUSH)  # pylint: disable=no-member
        push.connect(self.address)
        try:
            push.send(self.sentinel)
            log.debug("%s Sent sentinel to trigger log server shutdown", self)
            if self.sentinel_event.wait(5) is not True:  # pragma: no cover
                log.warning(
                    "%s Failed to wait for the reception of the stop sentinel message. Stopping anyway.",
                    self,
                )
        finally:
            push.close(1500)
            context.term()
        self.running_event.clear()
        log.debug("%s Joining running thread...", self)
        self.running_thread.join(7)
        if self.running_thread.is_alive():  # pragma: no cover
            log.debug("%s The running thread is still alive. Waiting a little longer...", self)
            self.running_thread.join(5)
            if self.running_thread.is_alive():
                log.debug(
                    "%s The running thread is still alive. Exiting anyway and let GC take care of it",
                    self,
                )
        log.debug("%s Joining cleanup thread...", self)
        self.cleanup_thread.join(7)
        if self.cleanup_thread.is_alive():  # pragma: no cover
            log.debug("%s The cleanup thread is still alive. Waiting a little longer...", self)
            self.cleanup_thread.join(5)
            if self.cleanup_thread.is_alive():
                log.debug(
                    "%s The cleanup thread is still alive. Exiting anyway and let GC take care of it",
                    self,
                )
        log.debug("%s stopped", self)

    def get_events(self, patterns, after_time=None):
        """
        Get events from the internal store.

        :param ~collections.abc.Sequence pattern:
            An iterable of tuples in the form of ``("<daemon-id>", "<event-tag-pattern>")``, ie, which daemon ID
            we're targeting and the event tag pattern which will be passed to :py:func:`~fnmatch.fnmatch` to
            assert a match.
        :keyword ~datetime.datetime,float after_time:
            After which time to start matching events.
        :return set: A set of matched events
        """
        if after_time is None:
            after_time = datetime.utcnow()
        elif isinstance(after_time, float):
            after_time = datetime.utcfromtimestamp(after_time)
        after_time_iso = after_time.isoformat()
        log.debug(
            "%s is checking for event patterns happening after %s: %s",
            self,
            after_time_iso,
            set(patterns),
        )
        found_events = set()
        patterns = set(patterns)
        for event in copy.copy(self.store):
            if event.expired:
                # Too old, carry on
                continue
            if event.stamp < after_time:
                continue
            for pattern in set(patterns):
                _daemon_id, _pattern = pattern
                if event.daemon_id != _daemon_id:
                    continue
                if fnmatch.fnmatch(event.tag, _pattern):
                    log.debug("%s Found matching pattern: %s", self, pattern)
                    found_events.add(event)
        if found_events:
            log.debug(
                "%s found the following patterns happening after %s: %s",
                self,
                after_time_iso,
                found_events,
            )
        else:
            log.debug(
                "%s did not find any matching event patterns happening after %s",
                self,
                after_time_iso,
            )
        return found_events

    def wait_for_events(self, patterns, timeout=30, after_time=None):
        """
        Wait for a set of patterns to match or until timeout is reached.

        :param ~collections.abc.Sequence pattern:
            An iterable of tuples in the form of ``("<daemon-id>", "<event-tag-pattern>")``, ie, which daemon ID
            we're targeting and the event tag pattern which will be passed to :py:func:`~fnmatch.fnmatch` to
            assert a match.
        :keyword int,float timeout:
            The amount of time to wait for the events, in seconds.
        :keyword ~datetime.datetime,float after_time:
            After which time to start matching events.

        :return:
            An instance of :py:class:`~saltfactories.plugins.event_listener.MatchedEvents`.
        :rtype ~saltfactories.plugins.event_listener.MatchedEvents:
        """
        if after_time is None:
            after_time = datetime.utcnow()
        elif isinstance(after_time, float):
            after_time = datetime.utcfromtimestamp(after_time)
        after_time_iso = after_time.isoformat()
        log.debug(
            "%s is waiting for event patterns happening after %s: %s",
            self,
            after_time_iso,
            set(patterns),
        )
        found_events = set()
        patterns = set(patterns)
        timeout_at = time.time() + timeout
        while True:
            if not patterns:
                return True
            for event in copy.copy(self.store):
                if event.expired:
                    # Too old, carry on
                    continue
                if event.stamp < after_time:
                    continue
                for pattern in set(patterns):
                    _daemon_id, _pattern = pattern
                    if event.daemon_id != _daemon_id:
                        continue
                    if fnmatch.fnmatch(event.tag, _pattern):
                        log.debug("%s Found matching pattern: %s", self, pattern)
                        found_events.add(event)
                        patterns.remove((event.daemon_id, _pattern))
            if not patterns:
                break
            if time.time() > timeout_at:
                break
            time.sleep(0.5)
        return MatchedEvents(matches=found_events, missed=patterns)

    def register_auth_event_handler(self, master_id, callback):
        """
        Register a callback to run for every authentication event, to accept or reject the minion authenticating.

        :param str master_id:
            The master ID for which the callback should run
        :type callback: ~collections.abc.Callable
        :param callback:
            The function while should be called
        """
        self.auth_event_handlers[master_id] = callback

    def unregister_auth_event_handler(self, master_id):
        """
        Un-register the authentication event callback, if any, for the provided master ID.

        :param str master_id:
            The master ID for which the callback is registered
        """
        self.auth_event_handlers.pop(master_id, None)


@pytest.fixture(scope="session")
def event_listener(request):
    """
    Event listener session scoped fixture.

    All started daemons will forward their events into an instance of
    :py:class:`~saltfactories.plugins.event_listener.EventListener`.

    This fixture can be used to wait for events:

    .. code-block:: python

        def test_send(event_listener, salt_master, salt_minion, salt_call_cli):
            event_tag = random_string("salt/test/event/")
            data = {"event.fire": "just test it!!!!"}
            start_time = time.time()
            ret = salt_call_cli.run("event.send", event_tag, data=data)
            assert ret.returncode == 0
            assert ret.data
            assert ret.data is True

            event_pattern = (salt_master.id, event_tag)
            matched_events = event_listener.wait_for_events(
                [event_pattern], after_time=start_time, timeout=30
            )
            assert matched_events.found_all_events
            # At this stage, we got all the events we were waiting for


    And assert against those events events:

    .. code-block:: python

        def test_send(event_listener, salt_master, salt_minion, salt_call_cli):
            # ... check the example above for the initial code ...
            assert matched_events.found_all_events
            # At this stage, we got all the events we were waiting for
            for event in matched_events:
                assert event.data["id"] == salt_minion.id
                assert event.data["cmd"] == "_minion_event"
                assert "event.fire" in event.data["data"]
    """
    return request.config.pluginmanager.get_plugin("saltfactories-event-listener")


def pytest_configure(config):
    """
    Configure the plugins.
    """
    _event_listener = EventListener()
    config.pluginmanager.register(_event_listener, "saltfactories-event-listener")


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    """
    Start the event listener plugin.
    """
    _event_listener = session.config.pluginmanager.get_plugin("saltfactories-event-listener")
    _event_listener.start()


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session):
    """
    Stop the event listener plugin.
    """
    _event_listener = session.config.pluginmanager.get_plugin("saltfactories-event-listener")
    _event_listener.stop()
