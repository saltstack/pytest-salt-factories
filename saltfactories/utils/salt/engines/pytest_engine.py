# -*- coding: utf-8 -*-
"""
pytest_engine
~~~~~~~~~~~~~

Simple salt engine which will setup a socket to accept connections allowing us to know
when a daemon is up and running
"""
import atexit
import datetime
import logging
import threading

import zmq

try:
    from collections.abc import MutableMapping
except ImportError:
    # Py2 compat
    from collections import MutableMapping
try:
    import msgpack

    HAS_MSGPACK = True
except ImportError:
    HAS_MSGPACK = False

import salt.utils.event

try:
    import salt.utils.immutabletypes as immutabletypes
except ImportError:
    immutabletypes = None
try:
    from salt.utils.data import CaseInsensitiveDict
except ImportError:
    CaseInsensitiveDict = None


log = logging.getLogger(__name__)

__virtualname__ = "pytest"


def __virtual__():
    role = __opts__["__role"]
    pytest_key = "pytest-{}".format(role)
    if pytest_key not in __opts__:
        return False, "No '{}' key in opts dictionary".format(pytest_key)

    pytest_config = __opts__[pytest_key]
    if "returner_address" not in pytest_config:
        return False, "No 'returner_address' key in opts['{}'] dictionary".format(pytest_key)
    if HAS_MSGPACK is False:
        return False, "msgpack was not importable. Please install msgpack."
    return True


def start():
    opts = __opts__  # pylint: disable=undefined-variable
    try:
        pytest_engine = PyTestEventForwardEngine(opts=opts)
        pytest_engine.start()
    except Exception:  # pylint: disable=broad-except
        log.error("Failed to start PyTestEventForwardEngine", exc_info=True)
        raise


def ext_type_encoder(obj):
    """
    Convert any types that msgpack cannot handle on it's own
    """
    if isinstance(obj, (datetime.datetime, datetime.date)):
        # msgpack doesn't support datetime.datetime and datetime.date datatypes.
        return obj.strftime("%Y%m%dT%H:%M:%S.%f")
    # The same for immutable types
    elif immutabletypes is not None and isinstance(obj, immutabletypes.ImmutableDict):
        return dict(obj)
    elif immutabletypes is not None and isinstance(obj, immutabletypes.ImmutableList):
        return list(obj)
    elif immutabletypes is not None and isinstance(obj, immutabletypes.ImmutableSet):
        # msgpack can't handle set so translate it to tuple
        return tuple(obj)
    elif isinstance(obj, set):
        # msgpack can't handle set so translate it to tuple
        return tuple(obj)
    elif CaseInsensitiveDict is not None and isinstance(obj, CaseInsensitiveDict):
        return dict(obj)
    elif isinstance(obj, MutableMapping):
        return dict(obj)
    # Nothing known exceptions found. Let msgpack raise its own.
    return obj


class PyTestEventForwardEngine:

    __slots__ = ("opts", "id", "role", "returner_address", "running_event")

    def __init__(self, opts):
        self.opts = opts
        self.id = self.opts["id"]
        self.role = self.opts["__role"]
        self.returner_address = self.opts["pytest-{}".format(self.role)]["returner_address"]
        self.running_event = threading.Event()

    def __repr__(self):
        return "<{} role={!r} id={!r}, returner_address={!r} running={!r}>".format(
            self.__class__.__name__,
            self.role,
            self.id,
            self.returner_address,
            self.running_event.is_set(),
        )

    def start(self):
        if self.running_event.is_set():
            return
        log.info("%s is starting", self)
        atexit.register(self.stop)

        self.running_event.set()
        context = zmq.Context()
        push = context.socket(zmq.PUSH)
        log.debug("%s connecting PUSH socket to %s", self, self.returner_address)
        push.connect(self.returner_address)
        opts = self.opts.copy()
        opts["file_client"] = "local"
        with salt.utils.event.get_event(
            self.role,
            sock_dir=opts["sock_dir"],
            transport=opts["transport"],
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
                    forward = (self.id, tag, data)
                    try:
                        dumped = msgpack.dumps(forward, use_bin_type=True, default=ext_type_encoder)
                        push.send(dumped)
                        log.info("%s forwarded event: %r", self, forward)
                    except Exception:  # pylint: disable=broad-except
                        log.error("%s failed to forward event: %r", self, forward, exc_info=True)
        push.close(1500)
        context.term()

    def stop(self):
        if self.running_event.is_set() is False:
            return

        log.info("Stopping %s", self)
        self.running_event.clear()
        log.info("%s stopped", self)
