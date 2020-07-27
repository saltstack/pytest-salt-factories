"""
    saltfactories.utils.log_server
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Tornado Log Server Fixture
"""
import logging
import threading
import time
from contextlib import contextmanager

import msgpack
import zmq


log = logging.getLogger(__name__)


@contextmanager
def log_server_listener(log_server_host, log_server_port):

    address = "tcp://{}:{}".format(log_server_host, log_server_port)
    log.info("Processing logs at %s", address)

    def stop_server(address):
        log.debug("Stopping the multiprocessing logging queue listener at %s", address)
        context = zmq.Context()
        sender = context.socket(zmq.PUSH)
        sender.connect(address)
        try:
            sender.send(msgpack.dumps(None))
            log.info("Sent sentinel to trigger log server shutdown")
        finally:
            sender.close(1000)
            context.term()

    def process_logs(address, running_event):
        context = zmq.Context()
        puller = context.socket(zmq.PULL)
        exit_timeout_seconds = 5
        exit_timeout = None
        try:
            puller.bind(address)
        except zmq.ZMQError as exc:
            log.exception("Unable to bind to puller at %s", address)
            return
        try:
            running_event.set()
            while True:
                if not running_event.is_set():
                    if exit_timeout is None:
                        log.debug(
                            "Waiting %d seconds to process any remaning log messages "
                            "before exiting...",
                            exit_timeout_seconds,
                        )
                        exit_timeout = time.time() + exit_timeout_seconds

                    if time.time() >= exit_timeout:
                        log.debug(
                            "Unable to process remaining log messages in time. " "Exiting anyway."
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
                        log.info("Received the sentinel to shutdown the log server")
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
                except (EOFError, KeyboardInterrupt, SystemExit) as exc:
                    break
                except Exception as exc:  # pylint: disable=broad-except
                    log.warning(
                        "An exception occurred in the log server processing queue thread: %s",
                        exc,
                        exc_info=True,
                    )
        finally:
            puller.close(1)
            context.term()

    running_event = threading.Event()
    process_queue_thread = threading.Thread(target=process_logs, args=(address, running_event))
    process_queue_thread.start()

    # Wait for the thread to start
    if running_event.wait(5) is not True:
        running_event.clear()
        raise RuntimeError("Failed to start the log server")

    # Work it!
    yield

    log.info("Stopping the logging server process thread")
    stop_server(address)
    # Clear the running even, the log process thread know it should stop
    running_event.clear()
    log.info("Joining the logging server process thread")
    process_queue_thread.join(7)
    if not process_queue_thread.is_alive():
        log.debug("Stopped the log server")
    else:
        log.warning("The logging server thread is still running. Waiting a little longer...")
        process_queue_thread.join(5)
        if not process_queue_thread.is_alive():
            log.debug("Stopped the log server")
        else:
            log.warning("The logging server thread is still running...")
