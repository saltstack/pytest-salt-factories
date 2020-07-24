"""
    saltfactories.utils.log_server
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Tornado Log Server Fixture
"""
import logging
import threading
from contextlib import contextmanager

import msgpack
import zmq


log = logging.getLogger(__name__)


@contextmanager
def log_server_listener(log_server_host, log_server_port):
    def stop(host, port):
        address = "tcp://{}:{}".format(host, port)
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
        log.debug("Stopped the multiprocessing logging queue listener")

    def process_logs(host, port):
        address = "tcp://{}:{}".format(host, port)
        log.info("Processing logs at %s", address)
        context = zmq.Context()
        puller = context.socket(zmq.PULL)
        try:
            puller.bind(address)
        except zmq.ZMQError as exc:
            log.exception("Unable to bind to puller at %s", address)
            return
        try:
            while True:
                try:
                    msg = puller.recv()
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
                        "An exception occurred in the multiprocessing logging queue thread: %s",
                        exc,
                        exc_info=True,
                    )
        finally:
            puller.close(1)
            context.term()

    process_queue_thread = threading.Thread(
        target=process_logs, args=(log_server_host, log_server_port)
    )
    process_queue_thread.start()

    yield

    log.info("Stopping the logging server process thread")
    stop(log_server_host, log_server_port)
    log.info("Joining the logging server process thread")
    process_queue_thread.join()
    log.debug("The logging server process thread was successfully joined")
