# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import atexit
import logging

import salt.utils.msgpack as msgpack

try:
    import zmq

    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False


log = logging.getLogger(__name__)


class Connection(object):
    def __init__(self, address):
        self.address = address
        self.context = zmq.Context()
        self.push = self.context.socket(zmq.PUSH)
        log.debug("Connecting PUSH socket to %s", self.address)
        self.push.connect(self.address)
        atexit.register(self.close)

    def __getstate__(self):
        return {"address": self.address}

    def __setstate__(self, state):
        return self.__init__(state["address"])

    def close(self):
        if self.push:
            self.push.close(1)
            self.push = None
        if self.context:
            self.context.term()
            self.context = None

    def send(self, data):
        self.push.send(data)


__virtualname__ = "pytest_returner"


def __virtual__():
    if msgpack.HAS_MSGPACK is False:
        msg = "The 'msgpack' python library is not available."
        log.warning(msg)
        return False, msg
    if HAS_ZMQ is False:
        msg = "The 'pyzmq' python library is not available."
        log.warning(msg)
        return False, msg
    log.warning("%s should be good to load", __virtualname__)
    return True


def _get_conn(opts, ctx):
    if "zmq_conn" not in ctx:
        conn = Connection(opts["pytest_returner_address"])
        ctx["conn"] = conn
    else:
        conn = ctx["zmq_conn"]
    return conn


def event_return(events):
    """
    Requires that configuration be enabled via 'event_return'
    option in master config.
    """
    _events = []
    for event in events:
        tag = event.get("tag", "")
        data = event.get("data", "")
        _events.append((__opts__["id"], tag, data))

    context = zmq.Context()
    push = _get_conn(__opts__, __context__)
    push.send(msgpack.dumps(_events, use_bin_type=True))
