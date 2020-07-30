# -*- coding: utf-8 -*-
"""
pytest_engine
~~~~~~~~~~~~~

Simple salt engine which will setup a socket to accept connections allowing us to know
when a daemon is up and running
"""
import atexit
import logging

import zmq

try:
    from salt.ext.tornado import gen
    from salt.ext.tornado import ioloop
except ImportError:
    # This likely due to running backwards compatibility tests against older minions
    from tornado import gen
    from tornado import ioloop

try:
    import salt.utils.asynchronous

    HAS_SALT_ASYNC = True
except ImportError:
    HAS_SALT_ASYNC = False
try:
    import msgpack

    HAS_MSGPACK = True
except ImportError:
    HAS_MSGPACK = False


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
    pytest_engine = PyTestEngine(__opts__)  # pylint: disable=undefined-variable
    pytest_engine.start()


class PyTestEngine:
    def __init__(self, opts):
        self.opts = opts
        self.id = opts["id"]
        self.role = opts["__role"]
        self.returner_address = opts["pytest-{}".format(self.role)]["returner_address"]

    def start(self):
        log.info(
            "Starting Pytest Event Forwarder Engine(forwarding to %s) on daemon with role %r and ID %r",
            self.returner_address,
            self.role,
            self.id,
        )
        self.io_loop = ioloop.IOLoop()
        self.io_loop.make_current()
        self.io_loop.add_callback(self._start)
        atexit.register(self.stop)
        self.io_loop.start()

    @gen.coroutine
    def _start(self):
        self.context = zmq.Context()
        self.push = self.context.socket(zmq.PUSH)
        log.debug("Connecting PUSH socket to %s", self.returner_address)
        self.push.connect(self.returner_address)
        minion_opts = self.opts.copy()
        minion_opts["file_client"] = "local"
        self.event = salt.utils.event.get_event(
            "master", opts=minion_opts, io_loop=self.io_loop, listen=True
        )
        self.event.subscribe("")
        self.event.set_event_handler(self.handle_event)
        event_tag = "salt/master/{}/start".format(self.id)
        log.info("Firing event on engine start. Tag: %s", event_tag)
        load = {"id": self.id, "tag": event_tag, "data": {}}
        self.event.fire_event(load, event_tag)

    def stop(self):
        push = self.push
        context = self.context
        event = self.event
        self.push = self.context = self.event = None
        if event:
            event.unsubscribe("")
            event.destroy()
        if push and context:
            push.close(1000)
            context.term()
            self.io_loop.add_callback(self.io_loop.stop)

    @gen.coroutine
    def handle_event(self, payload):
        tag, data = salt.utils.event.SaltEvent.unpack(payload)
        log.debug("Received Event; TAG: %r DATA: %r", tag, data)
        forward = msgpack.dumps((self.id, tag, data), use_bin_type=True)
        yield self.push.send(forward)
