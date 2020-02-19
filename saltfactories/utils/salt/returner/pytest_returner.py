# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging

import salt.utils.msgpack as msgpack

try:
    import zmq

    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False


log = logging.getLogger(__name__)


def _get_conn(opts, ctx):
    if "zmq_context" not in ctx:
        context = zmq.Context()
        ctx["zmq_context"] = context
    else:
        context = ctx["zmq_context"]

    if "zmq_socket" not in ctx:
        push = context.socket(zmq.PUSH)
        log.debug("Connecting PUSH socket to %s", opts["pytest_returner_address"])
        push.connect(opts["pytest_returner_address"])
        ctx["zmq_socket"] = push
    else:
        push = ctx["zmq_socket"]
    return push


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
