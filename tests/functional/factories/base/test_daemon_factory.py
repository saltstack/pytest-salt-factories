import functools
import pprint
import sys
import time

import psutil
import pytest

from saltfactories.factories.base import DaemonFactory
from saltfactories.utils import platform

PROCESS_START_TIMEOUT = 2


def kill_children(procs):
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
    daemon = DaemonFactory(**factory_kwargs)
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
    for child in list(children):
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
    daemon = DaemonFactory(**factory_kwargs)
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
