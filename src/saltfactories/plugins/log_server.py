"""
    saltfactories.plugins.log_server
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Log Server Plugin
"""
import logging
import threading

import attr
import msgpack
import pytest
import zmq

from saltfactories.utils import platform
from saltfactories.utils import ports
from saltfactories.utils import time

log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True, hash=True)
class LogServer:
    log_host = attr.ib()
    log_port = attr.ib()
    log_level = attr.ib()
    running_event = attr.ib(init=False, repr=False, hash=False)
    sentinel_event = attr.ib(init=False, repr=False, hash=False)
    process_queue_thread = attr.ib(init=False, repr=False, hash=False)

    @log_host.default
    def _default_log_host(self):
        if platform.is_windows():
            # Windows cannot bind to 0.0.0.0
            return "127.0.0.1"
        return "0.0.0.0"

    @log_port.default
    def _default_log_port(self):
        return ports.get_unused_localhost_port()

    def start(self):
        log.info("%s starting...", self)
        self.sentinel_event = threading.Event()
        self.running_event = threading.Event()
        self.process_queue_thread = threading.Thread(target=self.process_logs)
        self.process_queue_thread.start()
        # Wait for the thread to start
        if self.running_event.wait(5) is not True:
            self.running_event.clear()
            raise RuntimeError("Failed to start the log server")
        log.info("%s started", self)

    def stop(self):
        log.info("%s stopping...", self)
        address = "tcp://{}:{}".format(self.log_host, self.log_port)
        context = zmq.Context()
        sender = context.socket(zmq.PUSH)
        sender.connect(address)
        try:
            sender.send(msgpack.dumps(None))
            log.debug("%s Sent sentinel to trigger log server shutdown", self)
            if self.sentinel_event.wait(5) is not True:
                log.warning(
                    "%s Failed to wait for the reception of the stop sentinel message. Stopping anyway.",
                    self,
                )
        finally:
            sender.close(1000)
            context.term()

        # Clear the running even, the log process thread know it should stop
        self.running_event.clear()
        log.info("%s Joining the logging server process thread", self)
        self.process_queue_thread.join(7)
        if not self.process_queue_thread.is_alive():
            log.debug("%s Stopped", self)
        else:
            log.warning(
                "%s The logging server thread is still running. Waiting a little longer...", self
            )
            self.process_queue_thread.join(5)
            if not self.process_queue_thread.is_alive():
                log.debug("%s Stopped", self)
            else:
                log.warning("%s The logging server thread is still running...", self)

    def process_logs(self):
        address = "tcp://{}:{}".format(self.log_host, self.log_port)
        context = zmq.Context()
        puller = context.socket(zmq.PULL)
        exit_timeout_seconds = 5
        exit_timeout = None
        try:
            puller.bind(address)
        except zmq.ZMQError:
            log.exception("%s Unable to bind to puller at %s", self, address)
            return
        try:
            self.running_event.set()
            while True:
                if not self.running_event.is_set():
                    if exit_timeout is None:
                        log.debug(
                            "%s Waiting %d seconds to process any remaning log messages "
                            "before exiting...",
                            self,
                            exit_timeout_seconds,
                        )
                        exit_timeout = time.time() + exit_timeout_seconds

                    if time.time() >= exit_timeout:
                        log.debug(
                            "%s Unable to process remaining log messages in time. Exiting anyway.",
                            self,
                        )
                        break
                try:
                    try:
                        msg = puller.recv(flags=zmq.NOBLOCK)
                    except zmq.ZMQError as exc:
                        if exc.errno != zmq.EAGAIN:
                            raise
                        time.sleep(0.25)
                        continue
                    if msgpack.version >= (0, 5, 2):
                        record_dict = msgpack.loads(msg, raw=False)
                    else:
                        record_dict = msgpack.loads(msg, encoding="utf-8")
                    if record_dict is None:
                        # A sentinel to stop processing the queue
                        log.info("%s Received the sentinel to shutdown", self)
                        self.sentinel_event.set()
                        break
                    try:
                        record_dict["message"]
                    except KeyError:
                        # This log record was msgpack dumped from Py2
                        for key, value in record_dict.copy().items():
                            skip_update = True
                            if isinstance(value, bytes):
                                value = value.decode("utf-8")
                                skip_update = False
                            if isinstance(key, bytes):
                                key = key.decode("utf-8")
                                skip_update = False
                            if skip_update is False:
                                record_dict[key] = value
                    # Just log everything, filtering will happen on the main process
                    # logging handlers
                    record = logging.makeLogRecord(record_dict)
                    logger = logging.getLogger(record.name)
                    logger.handle(record)
                except (EOFError, KeyboardInterrupt, SystemExit):
                    break
                except Exception as exc:  # pylint: disable=broad-except
                    log.warning(
                        "%s An exception occurred in the processing queue thread: %s",
                        self,
                        exc,
                        exc_info=True,
                    )
        finally:
            puller.close(1)
            context.term()
        log.debug("%s Process log thread terminated", self)


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    # If PyTest has no logging configured, default to ERROR level
    levels = [logging.ERROR]
    logging_plugin = config.pluginmanager.get_plugin("logging-plugin")
    try:
        level = logging_plugin.log_cli_handler.level
        if level is not None:
            levels.append(level)
    except AttributeError:
        # PyTest CLI logging not configured
        pass
    try:
        level = logging_plugin.log_file_level
        if level is not None:
            levels.append(level)
    except AttributeError:
        # PyTest Log File logging not configured
        pass

    if logging.NOTSET in levels:
        # We don't want the NOTSET level on the levels
        levels.pop(levels.index(logging.NOTSET))

    log_level = logging.getLevelName(min(levels))

    log_server = LogServer(log_level=log_level)
    config.pluginmanager.register(log_server, "saltfactories-log-server")


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    log_server = session.config.pluginmanager.get_plugin("saltfactories-log-server")
    log_server.start()


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session):
    log_server = session.config.pluginmanager.get_plugin("saltfactories-log-server")
    log_server.stop()
