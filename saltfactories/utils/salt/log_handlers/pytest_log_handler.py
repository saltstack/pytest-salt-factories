# -*- coding: utf-8 -*-
'''
pytestsalt.salt.log_handlers.pytest_log_handler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Salt External Logging Handler
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import atexit
import copy
import logging
import os
import socket

# Import 3rd-party libs
import msgpack
import zmq

# Import Salt libs
import salt.log.setup
import salt.utils.stringutils

try:
    from salt.log.handlers import ZMQHandler as _ZMQHandler
except ImportError:
    from salt.log.mixins import ExcInfoOnLogLevelFormatMixIn, NewStyleClassMixIn

    class _ZMQHandler(ExcInfoOnLogLevelFormatMixIn, logging.Handler, NewStyleClassMixIn):
        def __init__(self, host='127.0.0.1', port=3330):
            logging.Handler.__init__(self)
            self.context = zmq.Context()
            self.sender = self.context.socket(zmq.PUSH)
            self.sender.connect('tcp://{}:{}'.format(host, port))

        def stop(self):
            self.sender.close(0)
            self.context.term()

        def prepare(self, record):
            msg = self.format(record)
            record = copy.copy(record)
            record.message = msg
            record.msg = msg
            record.args = None
            record.exc_info = None
            record.exc_text = None
            return record

        def emit(self, record):
            '''
            Emit a record.
            Writes the LogRecord to the queue, preparing it for pickling first.
            '''
            try:
                record = self.prepare(record)
                self.sender.send(msgpack.dumps(record.__dict__, use_bin_type=True))
            except Exception:  # pylint: disable=broad-except
                self.handleError(record)


class ZMQHandler(_ZMQHandler):
    def __init__(self, prefix, *args, **kwargs):
        self.prefix = prefix
        _ZMQHandler.__init__(self, *args, **kwargs)

    def prepare(self, record):
        record = _ZMQHandler.prepare(self, record)
        record.msg = record.message = '[{}] {}'.format(
            salt.utils.stringutils.to_unicode(self.prefix),
            salt.utils.stringutils.to_unicode(record.msg),
        )
        return record


__virtualname__ = 'pytest_log_handler'

log = logging.getLogger(__name__)


def __virtual__():
    if 'pytest' not in __opts__:
        return False, "No 'pytest' key in opts dictionary"
    if 'log' not in __opts__['pytest']:
        return False, "No 'log' key  in 'pytest' opts dictionary"
    if 'port' not in __opts__['pytest']['log']:
        return False, "No 'port' key  in pytest 'log' opts dictionary"
    return True


def setup_handlers():
    host_addr = __opts__['pytest']['log'].get('host')
    if not host_addr:
        import subprocess

        if __opts__['pytest_windows_guest'] is True:
            proc = subprocess.Popen('ipconfig', stdout=subprocess.PIPE)
            for line in proc.stdout.read().strip().encode(__salt_system_encoding__).splitlines():
                if 'Default Gateway' in line:
                    parts = line.split()
                    host_addr = parts[-1]
                    break
        else:
            proc = subprocess.Popen(
                "netstat -rn | grep -E '^0.0.0.0|default' | awk '{ print $2 }'",
                shell=True,
                stdout=subprocess.PIPE,
            )
            host_addr = proc.stdout.read().strip().encode(__salt_system_encoding__)
    host_port = __opts__['pytest']['log']['port']
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host_addr, host_port))
    except socket.error as exc:
        # Don't even bother if we can't connect
        log.warning('Cannot connect back to log server: %s', exc)
        return
    finally:
        sock.close()

    pytest_log_prefix = os.environ.get('PYTEST_LOG_PREFIX') or __opts__['pytest']['log'].get(
        'prefix'
    )
    level = salt.log.setup.LOG_LEVELS[(__opts__['pytest']['log'].get('level') or 'error').lower()]
    handler = ZMQHandler(pytest_log_prefix, host_addr, host_port)
    handler.setLevel(level)
    atexit.register(handler.stop)
    return handler
