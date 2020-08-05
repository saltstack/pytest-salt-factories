import functools
import pprint
import re
import sys
import time

import psutil
import pytest

from saltfactories.exceptions import FactoryNotStarted
from saltfactories.factories.base import DaemonFactory
from saltfactories.utils import platform

PROCESS_START_TIMEOUT = 2


def kill_children(procs):  # pragma: no cover
    _, alive = psutil.wait_procs(procs, timeout=3)
    for p in alive:
        p.kill()


def test_daemon_process_termination(request, tempfiles):
    primary_childrend_count = 5
    secondary_children_count = 3
    script = tempfiles.makepyfile(
        """
        #!{shebang}
        # coding=utf-8

        import time
        import multiprocessing

        def spin():
            while True:
                try:
                    time.sleep(0.25)
                except KeyboardInterrupt:
                    break

        def spin_children():
            procs = []
            for idx in range({secondary_children_count}):
                proc = multiprocessing.Process(target=spin)
                proc.daemon = True
                proc.start()
                procs.append(proc)

            while True:
                try:
                    time.sleep(0.25)
                except KeyboardInterrupt:
                    break


        def main():
            procs = []

            for idx in range({primary_childrend_count}):
                proc = multiprocessing.Process(target=spin_children)
                procs.append(proc)
                proc.start()

            while True:
                try:
                    time.sleep(0.25)
                except KeyboardInterrupt:
                    break

            # We're not terminating child processes on purpose. Our code should handle it.

        # Support for windows test runs
        if __name__ == '__main__':
            multiprocessing.freeze_support()
            main()
        """.format(
            shebang=sys.executable,
            primary_childrend_count=primary_childrend_count,
            secondary_children_count=secondary_children_count,
        ),
        executable=True,
    )
    if not platform.is_windows():
        factory_kwargs = dict(cli_script_name=script)
    else:
        # Windows don't know how to handle python scripts directly
        factory_kwargs = dict(cli_script_name=sys.executable, base_script_args=[script])
    daemon = DaemonFactory(start_timeout=1, **factory_kwargs)
    daemon.start()
    daemon_pid = daemon.pid
    # Make sure the daemon is terminated no matter what
    request.addfinalizer(daemon.terminate)
    # Allow the script to start
    time.sleep(PROCESS_START_TIMEOUT)
    assert psutil.pid_exists(daemon_pid)
    proc = psutil.Process(daemon_pid)
    children = proc.children(recursive=True)
    request.addfinalizer(functools.partial(kill_children, children))
    assert len(children) == primary_childrend_count + (
        primary_childrend_count * secondary_children_count
    )
    daemon.terminate()
    assert psutil.pid_exists(daemon_pid) is False
    for child in list(children):  # pragma: no cover
        if psutil.pid_exists(child.pid):
            continue
        children.remove(child)
    assert not children, "len(children)=={} != 0\n{}".format(
        len(children), pprint.pformat(children)
    )


@pytest.mark.skip("Will debug later")
def test_daemon_process_termination_parent_killed(request, tempfiles):

    primary_childrend_count = 5
    secondary_children_count = 3
    script = tempfiles.makepyfile(
        """
        #!{shebang}
        # coding=utf-8

        import time
        import multiprocessing

        def spin():
            while True:
                try:
                    time.sleep(0.25)
                except KeyboardInterrupt:
                    break

        def spin_children():
            procs = []
            for idx in range({secondary_children_count}):
                proc = multiprocessing.Process(target=spin)
                proc.daemon = True
                proc.start()
                procs.append(proc)

            while True:
                try:
                    time.sleep(0.25)
                except KeyboardInterrupt:
                    break

        def main():
            procs = []

            for idx in range({primary_childrend_count}):
                proc = multiprocessing.Process(target=spin_children)
                procs.append(proc)
                proc.start()

            while True:
                try:
                    time.sleep(0.25)
                except KeyboardInterrupt:
                    break

            # We're not terminating child processes on purpose. Our code should handle it.

        # Support for windows test runs
        if __name__ == '__main__':
            multiprocessing.freeze_support()
            main()
        """.format(
            shebang=sys.executable,
            primary_childrend_count=primary_childrend_count,
            secondary_children_count=secondary_children_count,
        ),
        executable=True,
    )
    if not platform.is_windows():
        factory_kwargs = dict(cli_script_name=script)
    else:
        # Windows don't know how to handle python scripts directly
        factory_kwargs = dict(cli_script_name=sys.executable, base_script_args=[script])
    daemon = DaemonFactory(start_timeout=1, **factory_kwargs)
    daemon.start()
    daemon_pid = daemon.pid
    # Make sure the daemon is terminated no matter what
    request.addfinalizer(daemon.terminate)
    # Allow the script to start
    time.sleep(PROCESS_START_TIMEOUT)
    assert psutil.pid_exists(daemon_pid)
    proc = psutil.Process(daemon_pid)
    children = proc.children(recursive=True)
    request.addfinalizer(functools.partial(kill_children, children))
    assert len(children) == primary_childrend_count + (
        primary_childrend_count * secondary_children_count
    )
    # Pretend the parent process died.
    proc.kill()
    time.sleep(0.5)
    # We should should still be able to terminate all child processes
    daemon.terminate()
    assert psutil.pid_exists(daemon_pid) is False
    psutil.wait_procs(children, timeout=3)
    for child in list(children):
        if psutil.pid_exists(child.pid):
            continue
        children.remove(child)
    assert not children, "len(children)=={} != 0\n{}".format(
        len(children), pprint.pformat(children)
    )


@pytest.mark.parametrize("start_timeout", [0.1, 0.3])
def test_context_manager(request, tempfiles, start_timeout):
    script = tempfiles.makepyfile(
        r"""
        # coding=utf-8

        import sys
        import time
        import multiprocessing

        def main():
            time.sleep(3)
            sys.stdout.write("Done!\n")
            sys.stdout.flush()
            sys.exit(0)

        # Support for windows test runs
        if __name__ == '__main__':
            multiprocessing.freeze_support()
            main()
        """,
        executable=True,
    )
    daemon = DaemonFactory(
        cli_script_name=sys.executable,
        base_script_args=[script],
        start_timeout=2,
        max_start_attempts=1,
        check_ports=[12345],
    )
    # Make sure the daemon is terminated no matter what
    request.addfinalizer(daemon.terminate)
    with pytest.raises(FactoryNotStarted) as exc:
        daemon.start(start_timeout=start_timeout)
    match = re.search(r".*\((?P<seconds>.*) seconds each\)", str(exc.value))
    assert match
    seconds = float(match.group("seconds"))
    # Must take at least start_timeout to start
    assert seconds >= start_timeout
    # Should not take more than start_timeout + 0.3 to start and fail
    assert float(seconds) < start_timeout + 0.3

    # And using a context manager?
    with pytest.raises(FactoryNotStarted) as exc:
        started = None
        with daemon.started(start_timeout=start_timeout):
            # We should not even be able to set the following variable
            started = False  # pragma: no cover
    assert started is None
    match = re.search(r".*\((?P<seconds>.*) seconds each\)", str(exc.value))
    assert match
    seconds = float(match.group("seconds"))
    # Must take at least start_timeout to start
    assert seconds >= start_timeout
    # Should not take more than start_timeout + 0.3 to start and fail
    assert float(seconds) < start_timeout + 0.3


def test_context_manager_returns_class_instance(tempfiles):
    script = tempfiles.makepyfile(
        r"""
        # coding=utf-8

        import sys
        import time
        import multiprocessing

        def main():
            while True:
                try:
                    time.sleep(0.1)
                except KeyboardInterrupt:
                    break
            sys.stdout.write("Done!\n")
            sys.stdout.flush()
            sys.exit(0)

        # Support for windows test runs
        if __name__ == '__main__':
            multiprocessing.freeze_support()
            main()
        """,
        executable=True,
    )
    daemon = DaemonFactory(
        cli_script_name=sys.executable,
        base_script_args=[script],
        start_timeout=1,
        max_start_attempts=1,
    )

    # Without starting the factory
    started = d = None
    with pytest.raises(RuntimeError):
        with daemon as d:
            # We should not even be able to set the following variable
            started = d.is_running()  # pragma: no cover
    assert d is None
    assert started is None

    # After starting the factory
    started = False
    daemon.start()
    with daemon as d:
        # We should not even be able to set the following variable
        started = d.is_running()
    assert d.is_running() is False
    assert started is True

    # By starting the factory and passing timeout directly
    started = False
    with daemon.started(start_timeout=1) as d:
        # We should not even be able to set the following variable
        started = d.is_running()
    assert d.is_running() is False
    assert started is True

    # By starting the factory without any keyword arguments
    started = False
    with daemon.started() as d:
        # We should not even be able to set the following variable
        started = d.is_running()
    assert d.is_running() is False
    assert started is True
