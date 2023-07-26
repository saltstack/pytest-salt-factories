"""
Salt Factories Event Listener.

A salt events store for all daemons started by salt-factories
"""
import asyncio
import copy
import fnmatch
import logging
import threading
import weakref
from collections import deque
from datetime import datetime
from datetime import timedelta
from datetime import timezone

import attr
import msgpack.exceptions
import pytest
from pytestshellutils.utils import ports
from pytestshellutils.utils import time
from pytestskipmarkers.utils import platform

log = logging.getLogger(__name__)


def _convert_stamp(stamp):
    try:
        return datetime.fromisoformat(stamp).replace(tzinfo=timezone.utc)
    except AttributeError:  # pragma: no cover
        # Python < 3.7
        return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=timezone.utc)


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
        if datetime.now(tz=timezone.utc) < self._expire_at:
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


class EventListenerServer(asyncio.Protocol):
    """
    TCP Server to receive events forwarded.
    """

    def __init__(self, _event_listener, *args, **kwargs) -> None:
        self._event_listener = _event_listener
        super().__init__(*args, **kwargs)

    def connection_made(self, transport):
        """
        Connection established.
        """
        peername = transport.get_extra_info("peername")
        log.debug("Connection from %s", peername)
        # pylint: disable=attribute-defined-outside-init
        self.transport = transport
        self.unpacker = msgpack.Unpacker(raw=False, strict_map_key=False)
        # pylint: enable=attribute-defined-outside-init

    def data_received(self, data):
        """
        Received data.
        """
        try:
            self.unpacker.feed(data)
        except msgpack.exceptions.BufferFull:
            # Start over loosing some data?!
            self.unpacker = msgpack.Unpacker(  # pylint: disable=attribute-defined-outside-init
                raw=False,
                strict_map_key=False,
            )
            self.unpacker.feed(data)
        for payload in self.unpacker:
            if payload is None:
                self.transport.close()
                break
            self._event_listener._process_event_payload(payload)  # noqa: SLF001


@attr.s(kw_only=True, slots=True, hash=False)
class EventListener:
    """
    EventListener implementation.

    The ``EventListener`` is a service started by salt-factories which receives all the events of all the
    salt masters that it starts. The service runs throughout the whole pytest session.

    :keyword int timeout:
        How long, in seconds, should a forwarded event stay in the store, after which, it will be deleted.
    """

    timeout = attr.ib(default=120)
    host = attr.ib(init=False, repr=False)
    port = attr.ib(init=False, repr=False)
    address = attr.ib(init=False)
    store = attr.ib(init=False, repr=False, hash=False)
    running_event = attr.ib(init=False, repr=False, hash=False)
    running_thread = attr.ib(init=False, repr=False, hash=False)
    cleanup_thread = attr.ib(init=False, repr=False, hash=False)
    auth_event_handlers = attr.ib(init=False, repr=False, hash=False)
    server = attr.ib(init=False, repr=False, hash=False)
    server_running_event = attr.ib(init=False, repr=False, hash=False)

    @host.default
    def _default_host(self):
        if platform.is_windows():
            # Windows cannot bind to 0.0.0.0
            return "127.0.0.1"
        return "0.0.0.0"  # noqa: S104

    @port.default
    def _default_port(self):
        return ports.get_unused_localhost_port()

    @address.default
    def _default_address(self):
        return f"tcp://{self.host}:{self.port}"

    def __attrs_post_init__(self):
        """
        Post attrs initialization routines.
        """
        self.store = deque(maxlen=10000)
        self.running_event = threading.Event()
        self.cleanup_thread = threading.Thread(target=self._cleanup)
        self.auth_event_handlers = weakref.WeakValueDictionary()
        self.server_running_event = threading.Event()
        self.server = None
        self.running_thread = None

    def start_server(self):
        """
        Start the TCP server.
        """
        if self.server_running_event.is_set():
            return
        if self.running_thread:
            # If this attribute is set it means something happened to make
            # the server crash. Let's join the thread to restart it all.
            self.running_thread.join()
            self.running_thread = None
            log.info("%s server is re-starting", self)
        else:
            log.info("%s server is starting", self)
        self.running_thread = threading.Thread(target=self._run_loop_in_thread)
        self.running_thread.start()

    def _run_loop_in_thread(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run_server())
        except Exception:  # pylint: disable=broad-except
            self.server_running_event.clear()
            log.exception("%s: Exception raised while the running the server", self)
        finally:
            log.debug("shutdown asyncgens")
            loop.run_until_complete(loop.shutdown_asyncgens())
            log.debug("loop close")
            loop.close()

    async def _run_server(self):
        loop = asyncio.get_running_loop()
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
        self.server = await loop.create_server(
            lambda: EventListenerServer(self),
            self.host,
            self.port,
            start_serving=False,
        )
        try:
            async with self.server:
                loop.call_soon(self.server_running_event.set)
                log.debug("%s server is starting", self)
                await self.server.start_serving()
                while self.server_running_event.is_set():
                    await asyncio.sleep(1)
        finally:
            if self.server:
                self.server.close()
                log.debug("%s server await server close", self)
                await self.server.wait_closed()
                log.debug("%s server stoppped", self)
                self.server = None

    def _process_event_payload(self, decoded):
        try:
            daemon_id = decoded["id"]
            tag = decoded["tag"]
            data = decoded["data"]
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
                    except Exception:  # pragma: no cover pylint: disable=broad-except
                        log.exception(
                            "%s Error calling %r",
                            self,
                            auth_event_callback,
                        )
            log.debug(
                "%s store(id: %s) size after event received: %d",
                self,
                id(self.store),
                len(self.store),
            )
        except Exception:  # pragma: no cover pylint: disable=broad-except
            log.exception("%s Something funky happened", self)

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

    def __enter__(self):
        """
        Context manager support to start the event listener.
        """
        self.start()
        return self

    def __exit__(self, *_):
        """
        Context manager support to stop the event listener.
        """
        self.stop()

    def start(self):
        """
        Start the event listener.
        """
        if self.running_event.is_set():  # pragma: no cover
            return
        log.debug("%s is starting", self)
        self.running_event.set()
        self.start_server()
        # Wait for the thread to start
        if self.server_running_event.wait(5) is not True:
            self.server_running_event.clear()
            msg = "Failed to start the event listener"
            raise RuntimeError(msg)
        log.debug("%s is started", self)
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
        self.running_event.clear()
        self.server_running_event.clear()
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
            after_time = datetime.now(tz=timezone.utc)
        elif isinstance(after_time, float):
            after_time = datetime.fromtimestamp(after_time, tz=timezone.utc)
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
            after_time = datetime.now(tz=timezone.utc)
        elif isinstance(after_time, float):
            after_time = datetime.fromtimestamp(after_time, tz=timezone.utc)
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
def event_listener():
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
    with EventListener() as _event_listener:
        yield _event_listener


@pytest.fixture(autouse=True)
def _restart_event_listener(event_listener):  # pylint: disable=redefined-outer-name
    """
    Restart the `event_listener` TCP server is case it crashed.
    """
    try:
        yield
    finally:
        # No-op is the server hasn't stopped running
        event_listener.start_server()
