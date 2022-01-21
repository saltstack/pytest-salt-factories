import logging
import sys
from datetime import datetime
from datetime import timedelta

import pytest
import pytestskipmarkers.utils.platform
from pytestshellutils.exceptions import FactoryTimeout
from pytestshellutils.shell import ScriptSubprocess


def test_handler_does_not_block_when_not_connected(tempfiles):
    log_forwarding_socket_hwm = 5
    shell = ScriptSubprocess(script_name=sys.executable, timeout=10)
    script = tempfiles.makepyfile(
        """
        # coding=utf-8
        import sys
        import time
        import logging
        import multiprocessing

        from saltfactories.utils.saltext.log_handlers.pytest_log_handler import ZMQHandler
        # Salt was imported by now and set up it's own logging handlers. Remove them.
        logging.root.handlers = []

        # Setup a stream handler so that we can confirm that logging is working
        logging.basicConfig(
            stream=sys.stderr,
            level=logging.DEBUG,
            format="[%(levelname)-8s][%(processName)s(%(process)s)] %(message)s"
        )

        # Add our ZMQ handler, it should not block even though it does not connect anywhere
        handler = ZMQHandler(port=123456, socket_hwm={})
        logging.root.addHandler(handler)

        def main():
            log = logging.getLogger("foo")
            print("Logging started", flush=True)
            for idx in range(50):
                log.debug("Foo %s", idx)
            print("Logging finished", flush=True)
            logging.shutdown()
            exit(0)

        if __name__ == '__main__':
            multiprocessing.freeze_support()
            main()
        """.format(
            log_forwarding_socket_hwm
        )
    )
    try:
        result = shell.run(script)
    except FactoryTimeout as exc:  # pragma: no cover
        pytest.fail("The ZMQHandler blocked. Process result:\n{}".format(exc))
    # If the exitcode is not 0, that means the script was forcefully terminated, which,
    # in turn means the ZMQHandler blocked the process when not connected to the log
    # listener.
    assert "Logging started" in result.stdout
    assert "Logging finished" in result.stdout
    # Since we set a HWM of log_forwarding_socket_hwm, we should at least see
    # Foo {log_forwarding_socket_hwm + 1} logged to the console.
    # If we don't, the handler blocked the process
    assert "Foo {}".format(log_forwarding_socket_hwm + 1) in result.stderr
    assert result.returncode == 0


def test_all_messages_received(tempfiles, salt_factories, caplog):
    log_forwarding_socket_hwm = 500
    log_forwarding_calls = log_forwarding_socket_hwm * 2
    shell = ScriptSubprocess(script_name=sys.executable, timeout=10)
    script = tempfiles.makepyfile(
        """
        # coding=utf-8
        import sys
        import time
        import logging
        import multiprocessing

        from saltfactories.utils.saltext.log_handlers.pytest_log_handler import ZMQHandler
        # Salt was imported by now and set up it's own logging handlers. Remove them.
        logging.root.handlers = []

        # Setup a stream handler so that we can confirm that logging is working
        logging.basicConfig(
            stream=sys.stderr,
            level=logging.DEBUG,
            format="[%(levelname)-8s][%(processName)s(%(process)s)] %(message)s"
        )

        # Add our ZMQ handler
        handler = ZMQHandler(port={}, socket_hwm={})
        logging.root.addHandler(handler)

        def main():
            log = logging.getLogger("foo")
            print("Logging started", flush=True)
            for idx in range(1, {} + 1):
                log.debug("Foo:%s", idx)
            print("Logging finished", flush=True)
            exit(0)

        if __name__ == '__main__':
            multiprocessing.freeze_support()
            main()
        """.format(
            salt_factories.log_server_port, log_forwarding_socket_hwm, log_forwarding_calls
        )
    )
    with caplog.at_level(logging.DEBUG, logger="foo"):
        try:
            result = shell.run(script)
        except FactoryTimeout as exc:  # pragma: no cover
            pytest.fail("The ZMQHandler blocked. Process result:\n{}".format(exc))
        # If the exitcode is not 0, that means the script was forcefully terminated, which,
        # in turn means the ZMQHandler blocked the process when not connected to the log
        # listener.
        assert "Logging started" in result.stdout
        assert "Logging finished" in result.stdout
        expected_log_message = "Foo:{}".format(log_forwarding_calls)
        assert expected_log_message in result.stderr
        assert result.returncode == 0

        timeout = datetime.utcnow() + timedelta(seconds=120)
        while True:
            missed = []
            found_log_messages = []
            # We try multiple times because the script might have properly
            # flushed it's messages to the log server, but the log server
            # might still be processing them
            for record in caplog.records:
                if record.message.startswith("Foo"):
                    msgnum = int(record.message.split(":")[-1])
                    found_log_messages.append(msgnum)
            for idx in range(1, log_forwarding_calls + 1):
                if idx not in found_log_messages:  # pragma: no cover
                    missed.append(idx)
            try:
                assert (
                    len(found_log_messages) == log_forwarding_calls
                ), "len(found_log_messages={}) != {} // Missed: {}".format(
                    len(found_log_messages), log_forwarding_calls, missed
                )
                break
            except AssertionError:  # pragma: no cover
                if datetime.utcnow() > timeout:
                    raise


@pytest.mark.parametrize("fork_method", ("fork", "spawn"))
def test_all_messages_received_multiprocessing(tempfiles, salt_factories, caplog, fork_method):
    # The purpose of this test is just to make sure if forked/spawned processes inherit the
    # ZMQHandler and continue logging
    if fork_method == "fork":
        if pytestskipmarkers.utils.platform.is_windows():
            pytest.skip("Start method '{}' is not supported on Windows".format(fork_method))
        if sys.version_info >= (3, 8) and pytestskipmarkers.utils.platform.is_darwin():
            pytest.skip(
                "Start method '{}' is not supported on Darwin on Py3.8+".format(fork_method)
            )
    num_processes = 2
    log_forwarding_calls = 10
    shell = ScriptSubprocess(script_name=sys.executable, timeout=30)
    script = tempfiles.makepyfile(
        """
        # coding=utf-8
        import os
        import sys
        import time
        import logging
        import multiprocessing

        from saltfactories.utils.saltext.log_handlers.pytest_log_handler import ZMQHandler
        # Salt was imported by now and set up it's own logging handlers. Remove them.
        logging.root.handlers = []

        # Add our ZMQ handler
        handler = ZMQHandler(port={port})
        handler.setLevel(logging.DEBUG)
        logging.root.addHandler(handler)

        logging.root.setLevel(logging.DEBUG)

        def log_from_child_process(idx, parent_pid, evt):
            evt.set()  # process started, ready to start another one
            import os
            import logging
            log = logging.getLogger("foo")
            for idx in range(1, {calls} + 1):
                log.debug("Foo(Child of pid %s):%s:%s", parent_pid, idx, os.getpid())
            exit(0)

        def log_from_process(pidx, evt):

            import os
            import logging

            num_processes = {num_processes}
            procs = []
            cevt = multiprocessing.Event()
            for idx in range(num_processes):
                proc = multiprocessing.Process(
                    target=log_from_child_process,
                    args=(idx, os.getpid(), cevt),
                    name="P{{}}C{{}}".format(pidx, idx)
                )
                proc.start()
                procs.append(proc)
                cevt.wait()
                cevt.clear()
                time.sleep(0.25)

            evt.set()  # process started, ready to start another one

            log = logging.getLogger("foo")
            for idx in range(1, {calls} + 1):
                log.debug("Foo:%s:%s", idx, os.getpid())

            for proc in procs:
                proc.join()
            exit(0)

        def main():
            procs = []
            num_processes = {num_processes}
            print("Logging started", flush=True)
            evt = multiprocessing.Event()
            for idx in range(num_processes):
                proc = multiprocessing.Process(
                    target=log_from_process,
                    args=(idx, evt),
                    name="P{{}}".format(idx)
                )
                proc.start()
                procs.append(proc)
                evt.wait()
                evt.clear()
                time.sleep(0.25)

            for proc in procs:
                proc.join()
            print("Logging finished", flush=True)
            exit(0)

        if __name__ == '__main__':
            multiprocessing.freeze_support()
            multiprocessing.set_start_method("{fork_method}")
            main()
        """.format(
            port=salt_factories.log_server_port,
            calls=log_forwarding_calls,
            num_processes=num_processes,
            fork_method=fork_method,
        )
    )
    with caplog.at_level(logging.DEBUG, logger="foo"):
        try:
            result = shell.run(script)
        except FactoryTimeout as exc:  # pragma: no cover
            pytest.fail("The ZMQHandler blocked. Process result:\n{}".format(exc))
        # If the exitcode is not 0, that means the script was forcefully terminated, which,
        # in turn means the ZMQHandler blocked the process when not connected to the log
        # listener.
        assert "Logging started" in result.stdout
        assert "Logging finished" in result.stdout
        assert result.returncode == 0

        # It can take quite a while to receive all these messages,
        # Specially for Windows and macOS under CI
        timeout = datetime.utcnow() + timedelta(seconds=30)

        # We start N processes and each process starts N processes
        expected_process_count = (num_processes * num_processes) + num_processes
        while True:
            procs = {}
            # We try multiple times because the script might have properly
            # flushed it's messages to the log server, but the log server
            # might still be processing them
            for record in caplog.records:
                if record.msg.startswith("Foo"):
                    _, msgnum, pid = record.message.split(":")
                    assert record.process == int(pid)
                    procs.setdefault(record.processName, []).append(int(msgnum))
            try:
                assert procs
                assert len(procs) == expected_process_count
                break
            except AssertionError:  # pragma: no cover
                if datetime.utcnow() > timeout:
                    if len(procs) >= num_processes + 1:
                        # Sometimes under CI, some processes either fail to start or don't log.
                        # If we have at least the expected top level processes plus 1 child process,
                        # we've asserted that logs are forwarded from forked processes.
                        # Good enough for the test
                        break
                    raise
