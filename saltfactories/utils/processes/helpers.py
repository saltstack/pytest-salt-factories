# -*- coding: utf-8 -*-
"""
saltfactories.utils.processes.helpers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Process related helper functions
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import errno
import logging
import pprint
import signal
import sys
import time
import weakref

import psutil
import six

from saltfactories.exceptions import ProcessNotStarted
from saltfactories.utils import ports


log = logging.getLogger(__name__)


def collect_child_processes(pid):
    """
    Try to collect any started child processes of the provided pid
    """
    # Let's get the child processes of the started subprocess
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
    except psutil.NoSuchProcess:
        children = []
    return children


def _get_cmdline(proc):
    # pylint: disable=protected-access
    try:
        return proc._cmdline
    except AttributeError:
        # Cache the cmdline since that will be inaccessible once the process is terminated
        # and we use it in log calls
        try:
            cmdline = proc.cmdline()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # OSX is more restrictive about the above information
            cmdline = None
        except OSError:
            # On Windows we've seen something like:
            #   File " c: ... \lib\site-packages\pytestsalt\utils\__init__.py", line 182, in terminate_process
            #     terminate_process_list(process_list, kill=slow_stop is False, slow_stop=slow_stop)
            #   File " c: ... \lib\site-packages\pytestsalt\utils\__init__.py", line 130, in terminate_process_list
            #     _terminate_process_list(process_list, kill=kill, slow_stop=slow_stop)
            #   File " c: ... \lib\site-packages\pytestsalt\utils\__init__.py", line 78, in _terminate_process_list
            #     cmdline = process.cmdline()
            #   File " c: ... \lib\site-packages\psutil\__init__.py", line 786, in cmdline
            #     return self._proc.cmdline()
            #   File " c: ... \lib\site-packages\psutil\_pswindows.py", line 667, in wrapper
            #     return fun(self, *args, **kwargs)
            #   File " c: ... \lib\site-packages\psutil\_pswindows.py", line 745, in cmdline
            #     ret = cext.proc_cmdline(self.pid, use_peb=True)
            #   OSError: [WinError 299] Only part of a ReadProcessMemory or WriteProcessMemory request was completed: 'originated from ReadProcessMemory(ProcessParameters)
            cmdline = None
        if not cmdline:
            try:
                cmdline = proc.as_dict()
            except psutil.NoSuchProcess:
                cmdline = "<could not be retrived; dead process: {}>".format(proc)
            except (psutil.AccessDenied, OSError):
                cmdline = weakref.proxy(proc)
        proc._cmdline = cmdline
    return proc._cmdline
    # pylint: enable=protected-access


def _terminate_process_list(process_list, kill=False, slow_stop=False):
    log.info(
        "Terminating process list:\n%s",
        pprint.pformat([_get_cmdline(proc) for proc in process_list]),
    )
    for process in process_list[:]:  # Iterate over copy of the list
        if not psutil.pid_exists(process.pid):
            process_list.remove(process)
            continue
        try:
            if not kill and process.status() == psutil.STATUS_ZOMBIE:
                # Zombie processes will exit once child processes also exit
                continue
            if kill:
                log.info("Killing process(%s): %s", process.pid, _get_cmdline(process))
                process.kill()
            else:
                log.info("Terminating process(%s): %s", process.pid, _get_cmdline(process))
                try:
                    if slow_stop:
                        # Allow coverage data to be written down to disk
                        process.send_signal(signal.SIGTERM)
                        try:
                            process.wait(2)
                        except psutil.TimeoutExpired:
                            if psutil.pid_exists(process.pid):
                                continue
                    else:
                        process.terminate()
                except OSError as exc:
                    if exc.errno not in (errno.ESRCH, errno.EACCES):
                        raise
            if not psutil.pid_exists(process.pid):
                process_list.remove(process)
        except psutil.NoSuchProcess:
            process_list.remove(process)


def terminate_process_list(process_list, kill=False, slow_stop=False):
    def on_process_terminated(proc):
        log.info(
            "Process %s terminated with exit code: %s",
            getattr(proc, "_cmdline", proc),
            proc.returncode,
        )

    # Try to terminate processes with the provided kill and slow_stop parameters
    log.info("Terminating process list. 1st step. kill: %s, slow stop: %s", kill, slow_stop)

    # Remove duplicates from the process list
    seen_pids = []
    start_count = len(process_list)
    for proc in process_list[:]:
        if proc.pid in seen_pids:
            process_list.remove(proc)
        seen_pids.append(proc.pid)
    end_count = len(process_list)
    if end_count < start_count:
        log.debug("Removed %d duplicates from the initial process list", start_count - end_count)

    _terminate_process_list(process_list, kill=kill, slow_stop=slow_stop)
    psutil.wait_procs(process_list, timeout=5, callback=on_process_terminated)

    if process_list:
        # If there's still processes to be terminated, retry and kill them if slow_stop is False
        log.info(
            "Terminating process list. 2nd step. kill: %s, slow stop: %s",
            slow_stop is False,
            slow_stop,
        )
        _terminate_process_list(process_list, kill=slow_stop is False, slow_stop=slow_stop)
        psutil.wait_procs(process_list, timeout=5, callback=on_process_terminated)

    if process_list:
        # If there's still processes to be terminated, just kill them, no slow stopping now
        log.info("Terminating process list. 3rd step. kill: True, slow stop: False")
        _terminate_process_list(process_list, kill=True, slow_stop=False)
        psutil.wait_procs(process_list, timeout=5, callback=on_process_terminated)

    if process_list:
        # In there's still processes to be terminated, log a warning about it
        log.warning("Some processes failed to properly terminate: %s", process_list)


def terminate_process(pid=None, process=None, children=None, kill_children=None, slow_stop=False):
    """
    Try to terminate/kill the started processe
    """
    children = children or []
    process_list = []

    if kill_children is None:
        # Always kill children if kill the parent process and kill_children was not set
        kill_children = True if slow_stop is False else kill_children

    if pid and not process:
        try:
            process = psutil.Process(pid)
            process_list.append(process)
        except psutil.NoSuchProcess:
            # Process is already gone
            process = None

    if kill_children:
        if process:
            children.extend(collect_child_processes(pid))
        if children:
            process_list.extend(children)

    if process_list:
        if process:
            log.info("Stopping process %s and respective children: %s", process, children)
        else:
            log.info("Terminating process list: %s", process_list)
        terminate_process_list(process_list, kill=slow_stop is False, slow_stop=slow_stop)


def start_daemon(
    cli_script_name,
    daemon_class,
    start_timeout=10,
    max_attempts=3,
    event_listener=None,
    **extra_daemon_class_kwargs
):
    """
    Returns a running process daemon

    Args:
        cli_script_name(str):
            The CLI script which starts the daemon
        daemon_class(:py:class:`~saltfactories.utils.processes.bases.FactoryDaemonScriptBase`):
            The class to use to instantiate the process daemon instance.
        start_timeout(int):
            The amount of time, in seconds, to wait, until a subprocess is considered as not started.
        max_attempts(int):
            How many times to attempt to start the daemon in case of failure
        event_listener(:py:class:`~saltfactories.utils.event_listener.EventListener`):
            An instance of :py:class:`~saltfactories.utils.event_listener.EventListener` in case the daemon
            is a salt daemon.
        **extra_daemon_class_kwargs(dict):
            Extra keyword arguments to pass to the ``daemon_class`` when instantiating it.

    Raises:
        ProcessNotStarted:
            Raised when a process fails to start or when the code used to confirm that the daemon is up also fails.
        RuntimeError:
            `RuntimeError` is raised when a process defines
            :py:meth:`~saltfactories.utils.processes.salts.SaltDaemonScriptBase.get_check_events` but no
            ``event_listener`` argument was passed.

    Returns:
        An instance of the ``daemon_class``, which is a subclass of
        :py:class:`~saltfactories.utils.processes.bases.FactoryDaemonScriptBase`
    """
    attempts = 0
    log_prefix = ""

    checks_start_time = time.time()
    while attempts <= max_attempts:  # pylint: disable=too-many-nested-blocks
        attempts += 1
        process = daemon_class(cli_script_name=cli_script_name, **extra_daemon_class_kwargs)
        log_prefix = process.get_log_prefix()
        log.info("%sStarting %r. Attempt: %s", log_prefix, process, attempts)
        start_time = time.time()
        process.start()
        if process.is_alive():
            try:
                try:
                    check_ports = process.get_check_ports()
                except AttributeError:
                    check_ports = False

                try:
                    check_events = list(process.get_check_events())
                except AttributeError:
                    check_events = False

                if not check_ports and not check_events:
                    connectable = True
                else:
                    connectable = None
                    if check_ports:
                        connectable = ports.check_connectable_ports(
                            check_ports, timeout=start_timeout
                        )

                    if check_events:
                        if not event_listener:
                            process.terminate()
                            raise RuntimeError(
                                "Process {} want's to have events checked but no 'event_listener' was "
                                "passed to start_daemon()".format(process)
                            )
                        if connectable or connectable is None:
                            connectable = event_listener.wait_for_events(
                                process.get_check_events(),
                                after_time=start_time,
                                timeout=start_timeout,
                            )
                if connectable is False:
                    result = process.terminate()
                    if attempts >= max_attempts:
                        raise ProcessNotStarted(
                            "{}The {!r} has failed to confirm running status after {} attempts, which "
                            "took {:.2f} seconds".format(
                                log_prefix, process, attempts, time.time() - checks_start_time
                            ),
                            stdout=result.stdout,
                            stderr=result.stderr,
                        )
                    continue
            except ProcessNotStarted:
                six.reraise(*sys.exc_info())
            except Exception as exc:  # pylint: disable=broad-except
                log.exception(
                    "%sException caugth on %r: %s", log_prefix, process, exc, exc_info=True
                )
                result = process.terminate()
                if attempts >= max_attempts:
                    raise ProcessNotStarted(
                        "{}The {!r} has failed to confirm running status after {} attempts and raised an "
                        "exception: {}. Took {:.2f} seconds.".format(
                            log_prefix, process, attempts, str(exc), time.time() - start_time
                        ),
                        stdout=result.stdout,
                        stderr=result.stderr,
                        exc=sys.exc_info(),
                    )
                continue
            # A little breathing before returning the process
            time.sleep(0.125)
            log.info(
                "%sThe %r is running after %d attempts. Took %1.2f seconds",
                log_prefix,
                process,
                attempts,
                time.time() - checks_start_time,
            )
            break
        else:
            process.terminate()
            # A little pause before retrying
            time.sleep(1)
            continue
    else:
        stderr = stdout = None
        if process is not None:
            result = process.terminate()
            stderr = result.stderr
            stdout = result.stdout
        raise ProcessNotStarted(
            "{}The {!r} has failed to confirm running status after {} attempts, which "
            "took {:.2f} seconds.".format(
                log_prefix, process, attempts, time.time() - checks_start_time
            ),
            stdout=stdout,
            stderr=stderr,
        )
    return process
