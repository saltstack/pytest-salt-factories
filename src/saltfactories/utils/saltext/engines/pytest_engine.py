"""
Salt Factories Engine For Salt.

Simple salt engine which will setup a socket to accept connections allowing us to know
when a daemon is up and running
"""
import asyncio
import atexit
import datetime
import logging
import threading
import time
from collections import deque
from collections.abc import MutableMapping

import salt.utils.event
from salt.utils import immutabletypes

try:
    from salt.utils.data import CaseInsensitiveDict
except ImportError:  # pragma: no cover
    CaseInsensitiveDict = None

try:
    import msgpack

    HAS_MSGPACK = True
except ImportError:  # pragma: no cover
    HAS_MSGPACK = False

log = logging.getLogger(__name__)

__virtualname__ = "pytest"


def __virtual__():
    if HAS_MSGPACK is False:  # pragma: no cover
        return False, "msgpack was not importable. Please install msgpack."
    if "__role" not in __opts__:  # pragma: no cover
        return False, "The required '__role' key could not be found in the options dictionary"
    role = __opts__["__role"]
    pytest_key = "pytest-{}".format(role)
    if pytest_key not in __opts__:  # pragma: no cover
        return False, "No '{}' key in opts dictionary".format(pytest_key)

    pytest_config = __opts__[pytest_key]
    if "returner_address" not in pytest_config:
        return False, "No 'returner_address' key in opts['{}'] dictionary".format(pytest_key)
    return True


def start():
    """
    Method to start the engine.
    """
    opts = __opts__  # pylint: disable=undefined-variable
    try:
        pytest_engine = PyTestEventForwardEngine(opts=opts)
        pytest_engine.start()
    except Exception:  # pragma: no cover pylint: disable=broad-except
        log.exception("Failed to start PyTestEventForwardEngine")
        raise


def ext_type_encoder(obj):
    """
    Convert any types that msgpack cannot handle on it's own.
    """
    if isinstance(obj, (datetime.datetime, datetime.date)):
        # msgpack doesn't support datetime.datetime and datetime.date datatypes.
        return obj.strftime("%Y%m%dT%H:%M:%S.%f")
    # The same for immutable types
    if immutabletypes is not None:
        if isinstance(obj, immutabletypes.ImmutableDict):
            return dict(obj)
        if isinstance(obj, immutabletypes.ImmutableList):
            return list(obj)
        if isinstance(obj, immutabletypes.ImmutableSet):
            # msgpack can't handle set so translate it to tuple
            return tuple(obj)
    if isinstance(obj, set):
        # msgpack can't handle set so translate it to tuple
        return tuple(obj)
    if CaseInsensitiveDict is not None and isinstance(obj, CaseInsensitiveDict):
        return dict(obj)
    if isinstance(obj, MutableMapping):
        return dict(obj)
    # Nothing known exceptions found. Let msgpack raise its own.
    return obj


class PyTestEventForwardClient(asyncio.Protocol):
    """
    TCP Client to forward events.
    """

    def __init__(self, queue, client_running_event):
        self.queue = queue
        self.running = client_running_event
        self.task = None
        self.transport = None
        try:
            loop = asyncio.get_running_loop()
        except AttributeError:
            # Python < 3.7
            loop = asyncio.get_event_loop()
        self._connected = loop.create_future()
        self._disconnected = loop.create_future()

    def connection_made(self, transport):
        """
        Connection established.
        """
        peername = transport.get_extra_info("peername")
        log.debug("%s: Connected to %s", self.__class__.__name__, peername)
        self._connected.set_result(True)
        # pylint: disable=attribute-defined-outside-init
        self.transport = transport
        try:
            loop = asyncio.get_running_loop()
        except AttributeError:
            # Python < 3.7
            loop = asyncio.get_event_loop()
        self.task = loop.create_task(self._process_queue())
        # pylint: enable=attribute-defined-outside-init

    def connection_lost(self, exc):  # noqa: ARG002
        """
        Connection lost.
        """
        log.debug("%s: The server closed the connection", self.__class__.__name__)
        self._disconnected.set_result(True)
        if self.task is not None:
            self.task.cancel()

    async def wait_connected(self):
        """
        Wait until a connection to the server is successful.
        """
        return await self._connected

    async def wait_disconnected(self):
        """
        Wait until disconnected from the server.
        """
        return await self._disconnected

    async def _process_queue(self):
        self.running.set()
        log.info("%s: Now processing the queue", self.__class__.__name__)
        restarts = 0
        max_restarts = 10
        while True:
            if restarts > max_restarts:
                self._disconnected.set_result(True)
                break
            if not self.running.is_set():
                self._disconnected.set_result(True)
                break
            try:
                try:
                    payload = self.queue.popleft()
                except IndexError:
                    await asyncio.sleep(1)
                    continue
                if payload is None:
                    return
                dumped = msgpack.packb(payload, use_bin_type=True, default=ext_type_encoder)
                self.transport.write(dumped)
                log.debug("%s: forwarded event: %r", self.__class__.__name__, payload)
            except asyncio.CancelledError:
                break
            except Exception:  # pylint: disable=broad-except
                log.exception(
                    "%s: Caught exception while pulling data from queue",
                    self.__class__.__name__,
                )
                restarts += 1


class PyTestEventForwardEngine:
    """
    Salt Engine instance.
    """

    __slots__ = (
        "opts",
        "id",
        "role",
        "returner_address_host",
        "returner_address_port",
        "running_event",
        "client_running_event",
        "loop",
        "client",
        "queue",
        "running_thread",
    )

    def __init__(self, opts):
        self.opts = opts
        self.id = self.opts["id"]  # pylint: disable=invalid-name
        self.role = self.opts["__role"]
        returner_address = self.opts["pytest-{}".format(self.role)]["returner_address"]
        self.returner_address_host = returner_address["host"]
        self.returner_address_port = returner_address["port"]
        self.running_event = threading.Event()
        self.client_running_event = threading.Event()
        self.loop = asyncio.new_event_loop()
        self.client = None
        self.queue = deque(maxlen=1000)
        self.running_thread = threading.Thread(target=self._run_loop_in_thread, args=(self.loop,))

    def _run_loop_in_thread(self, loop):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run_client(loop))
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    async def _run_client(self, loop):
        log.debug(
            "%s client connecting to %s:%s",
            self.__class__.__name__,
            self.returner_address_host,
            self.returner_address_port,
        )
        self.client = PyTestEventForwardClient(self.queue, self.client_running_event)
        transport, _ = await loop.create_connection(
            lambda: self.client,
            self.returner_address_host,
            self.returner_address_port,
        )
        # Wait until the protocol signals that the connection
        # is lost and close the transport.
        try:
            await asyncio.wait_for(self.client.wait_connected(), timeout=15)
        except asyncio.TimeoutError:
            log.error("The client failed to connect to the server after 15 seconds")  # noqa: TRY400
            transport.close()
        else:
            try:
                log.info("%s client started", self.__class__.__name__)
                await self.client.wait_disconnected()
            finally:
                transport.close()

    def __repr__(self):  # noqa: D105
        return "<{} role={!r} id={!r}, returner_address='{}:{}' running={!r}>".format(
            self.__class__.__name__,
            self.role,
            self.id,
            self.returner_address_host,
            self.returner_address_port,
            self.running_event.is_set(),
        )

    def start(self):
        """
        Start the engine.
        """
        if self.running_event.is_set():
            return
        log.info("%s is starting", self)
        atexit.register(self.stop)

        self.running_event.set()
        self.running_thread.start()
        timeout_at = time.time() + 10
        while True:
            log.info("Waiting for %s.client to start...", self.__class__.__name__)
            if time.time() > timeout_at:
                msg = "Failed to start client"
                raise RuntimeError(msg)
            if self.client is None:
                time.sleep(1)
                continue
            if not self.client_running_event.is_set():
                time.sleep(1)
                continue
            break
        try:
            opts = self.opts.copy()
            opts["file_client"] = "local"
            with salt.utils.event.get_event(
                self.role,
                sock_dir=opts["sock_dir"],
                opts=opts,
                listen=True,
            ) as eventbus:
                if self.role == "master":
                    event_tag = "salt/master/{}/start".format(self.id)
                    log.info("%s firing event on engine start. Tag: %s", self, event_tag)
                    load = {"id": self.id, "tag": event_tag, "data": {}}
                    eventbus.fire_event(load, event_tag)
                log.info("%s started", self)
                while self.running_event.is_set():
                    for event in eventbus.iter_events(full=True, auto_reconnect=True):
                        if not event:
                            continue
                        tag = event["tag"]
                        data = event["data"]
                        log.debug("%s Received Event; TAG: %r DATA: %r", self, tag, data)
                        forward = {"id": self.id, "tag": tag, "data": data}
                        self.queue.append(forward)
        finally:
            if self.running_event.is_set():
                # Some exception happened, unset
                self.running_event.clear()

    def stop(self):
        """
        Stop the engine.
        """
        if self.running_event.is_set() is False:
            return

        log.info("Stopping %s", self)
        self.running_event.clear()
        self.queue.append(None)
        self.client_running_event.clear()
        self.running_thread.join()
        log.info("%s stopped", self)
