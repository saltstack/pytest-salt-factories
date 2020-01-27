# -*- coding: utf-8 -*-
"""
tests.functional.utils.processes.test_factory_daemon_script_base
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test saltfactories.utils.processes.FactoryDaemonScriptBase
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import functools
import os
import pprint
import stat
import sys
import time

import psutil

from saltfactories.utils.processes import FactoryDaemonScriptBase


def kill_children(procs):
    _, alive = psutil.wait_procs(procs, timeout=3)
    for p in alive:
        p.kill()


def test_daemon_process_termination(request, testdir):
    primary_childrend_count = 5
    secondary_children_count = 3
    script = testdir.makepyfile(
        """
        #!{shebang}
        # -*- coding: utf-8 -*-

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
        )
    ).strpath
    st = os.stat(script)
    os.chmod(script, st.st_mode | stat.S_IEXEC)
    daemon = FactoryDaemonScriptBase(script)
    daemon.start()
    daemon_pid = daemon.pid
    # Make sure the daemon is terminated no matter what
    request.addfinalizer(daemon.terminate)
    # Allow the script to start
    time.sleep(1)
    assert psutil.pid_exists(daemon_pid)
    daemon.wait_until_running()
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


def test_daemon_process_termination_parent_killed(request, testdir):

    primary_childrend_count = 5
    secondary_children_count = 3
    script = testdir.makepyfile(
        """
        #!{shebang}
        # -*- coding: utf-8 -*-

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
        )
    ).strpath
    st = os.stat(script)
    os.chmod(script, st.st_mode | stat.S_IEXEC)
    daemon = FactoryDaemonScriptBase(script)
    daemon.start()
    daemon_pid = daemon.pid
    # Make sure the daemon is terminated no matter what
    request.addfinalizer(daemon.terminate)
    # Allow the script to start
    time.sleep(1)
    assert psutil.pid_exists(daemon_pid)
    daemon.wait_until_running()
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
