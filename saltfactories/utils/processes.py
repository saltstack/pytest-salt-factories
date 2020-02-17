# -*- coding: utf-8 -*-
"""
saltfactories.utils.processes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Process related utilities
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import atexit
import errno
import json
import logging
import os
import pprint
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import weakref
from collections import namedtuple
from operator import itemgetter

import psutil
import pytest
import six
from tornado import iostream

from saltfactories.utils import compat


try:
    import setproctitle

    HAS_SETPROCTITLE = True
except ImportError:
    HAS_SETPROCTITLE = False

log = logging.getLogger(__name__)


def set_proc_title(title):
    if HAS_SETPROCTITLE is False:
        return
    setproctitle.setproctitle("[{}] - {}".format(title, setproctitle.getproctitle()))


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

            # Late import
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
    config,
    cli_script_name,
    daemon_class,
    fail_callable=None,
    start_timeout=10,
    slow_stop=True,
    environ=None,
    cwd=None,
    max_attempts=3,
    monitor_events=False,
):
    """
    Returns a running process daemon
    """
    attempts = 0
    log_prefix = ""

    if sys.platform.startswith("win"):
        # Double the start timeout on windows
        start_timeout = start_timeout * 2

    if fail_callable is None:
        fail_callable = pytest.fail

    while attempts <= max_attempts:  # pylint: disable=too-many-nested-blocks
        attempts += 1
        process = daemon_class(
            cli_script_name=cli_script_name,
            config=config,
            slow_stop=slow_stop,
            environ=environ,
            cwd=cwd,
        )
        log_prefix = process.log_prefix
        log.info("%sStarting %r. Attempt: %s", log_prefix, process, attempts)
        process.start()
        if process.is_alive():
            try:
                connectable = process.wait_until_running(
                    timeout=start_timeout, monitor_events=monitor_events
                )
                if connectable is False:
                    result = process.terminate()
                    if attempts >= max_attempts:
                        fail_callable(
                            "{}The {!r} has failed to confirm running status after {} attempts.\n"
                            "Process Output:\n>>>>> STDOUT >>>>>\n{}\n<<<<< STDOUT <<<<<\n"
                            ">>>>> STDERR >>>>>\n{}\n<<<<< STDERR <<<<<\n".format(
                                log_prefix, process, attempts, result.stdout, result.stderr,
                            )
                        )
                    continue
            except Exception as exc:  # pylint: disable=broad-except
                log.exception(
                    "%sException caugth on %r: %s", log_prefix, process, exc, exc_info=True
                )
                result = process.terminate()
                if attempts >= max_attempts:
                    fail_callable(
                        "{}The {!r} has failed to confirm running status after {} attempts and raised an "
                        "exception: {}.\n"
                        "Process Output:\n>>>>> STDOUT >>>>>\n{}\n<<<<< STDOUT <<<<<\n"
                        ">>>>> STDERR >>>>>\n{}\n<<<<< STDERR <<<<<\n".format(
                            log_prefix, process, attempts, str(exc), result.stdout, result.stderr,
                        )
                    )
                    return
                continue
            # A little breathing before returning the process
            time.sleep(0.5)
            log.info("%sThe %r is running after %d attempts", log_prefix, process, attempts)
            break
        else:
            process.terminate()
            time.sleep(1)
            continue
    else:
        if process is not None:
            result = process.terminate()
            fail_callable(
                "{}The {!r} has failed to confirm running status after {} attempts.\n"
                "Process Output:\n>>>>> STDOUT >>>>>\n{}\n<<<<< STDOUT <<<<<\n"
                ">>>>> STDERR >>>>>\n{}\n<<<<< STDERR <<<<<\n".format(
                    log_prefix, process, attempts, result.stdout, result.stderr
                )
            )
            return
        fail_callable(
            "{}The {!r} has failed to start after {} attempts".format(
                log_prefix, process, max_attempts
            )
        )
    return process


class Popen(subprocess.Popen):
    def __init__(self, *args, **kwargs):
        for key in ("stdout", "stderr"):
            if key in kwargs:
                raise RuntimeError(
                    "{}.Popen() does not accept {} as a valid keyword argument".format(
                        __name__, key
                    )
                )
        stdout = tempfile.SpooledTemporaryFile(512000)
        kwargs["stdout"] = stdout
        stderr = tempfile.SpooledTemporaryFile(512000)
        kwargs["stderr"] = stderr
        super(Popen, self).__init__(*args, **kwargs)
        self.__stdout = stdout
        self.__stderr = stderr
        compat.weakref.finalize(self, stdout.close)
        compat.weakref.finalize(self, stderr.close)

    def communicate(self, input=None):  # pylint: disable=arguments-differ
        super(Popen, self).communicate(input)
        stdout = stderr = None
        if self.__stdout:
            self.__stdout.seek(0)
            stdout = self.__stdout.read()

            if six.PY3:
                # pylint: disable=undefined-variable
                stdout = stdout.decode(__salt_system_encoding__)
                # pylint: enable=undefined-variable
        if self.__stderr:
            self.__stderr.seek(0)
            stderr = self.__stderr.read()

            if six.PY3:
                # pylint: disable=undefined-variable
                stderr = stderr.decode(__salt_system_encoding__)
                # pylint: enable=undefined-variable
        return stdout, stderr


class ProcessResult(namedtuple("ProcessResult", ("exitcode", "stdout", "stderr"))):
    """
    This class serves the purpose of having a common result class which will hold the
    resulting data from a subprocess command.
    """

    __slots__ = ()

    def __new__(cls, exitcode, stdout, stderr):
        if not isinstance(exitcode, int):
            raise ValueError("'exitcode' needs to be an integer, not '{}'".format(type(exitcode)))
        return super(ProcessResult, cls).__new__(cls, exitcode, stdout, stderr)

    # These are copied from the namedtuple verbose output in order to quiet down PyLint
    exitcode = property(itemgetter(0), doc="ShellResult exit code property")
    stdout = property(itemgetter(1), doc="ShellResult stdout property")
    stderr = property(itemgetter(2), doc="ShellResult stderr property")


class ShellResult(namedtuple("ShellResult", ("exitcode", "stdout", "stderr", "json"))):
    """
    This class serves the purpose of having a common result class which will hold the
    resulting data from a subprocess command.
    """

    __slots__ = ()

    def __new__(cls, exitcode, stdout, stderr, json):
        if not isinstance(exitcode, int):
            raise ValueError("'exitcode' needs to be an integer, not '{}'".format(type(exitcode)))
        return super(ShellResult, cls).__new__(cls, exitcode, stdout, stderr, json)

    # These are copied from the namedtuple verbose output in order to quiet down PyLint
    exitcode = property(itemgetter(0), doc="ShellResult exit code property")
    stdout = property(itemgetter(1), doc="ShellResult stdout property")
    stderr = property(itemgetter(2), doc="ShellResult stderr property")
    json = property(itemgetter(3), doc="ShellResult stdout JSON decoded, when parseable.")

    def __eq__(self, other):
        """
        Allow comparison against the parsed JSON or the output
        """
        if self.json:
            return self.json == other
        return self.stdout == other


class FactoryProcess(object):
    """
    Base class for subprocesses
    """

    def __init__(
        self,
        cli_script_name,
        config=None,
        slow_stop=True,
        environ=None,
        cwd=None,
        fail_callable=None,
    ):
        self.cli_script_name = cli_script_name
        if config is None:
            config = {}
        self.config = config
        if "__role" in config:
            pytest_config_key = "pytest-{}".format(config["__role"])
            log_prefix = config.get(pytest_config_key, {}).get("log", {}).get("prefix") or ""
            if log_prefix:
                log_prefix = "[{}] ".format(log_prefix)
        else:
            log_prefix = ""
        self.log_prefix = log_prefix
        self.slow_stop = slow_stop
        self.environ = environ or os.environ.copy()
        # We really do not want buffered output
        self.environ.setdefault(str("PYTHONUNBUFFERED"), str("1"))
        self.cwd = cwd or os.getcwd()
        self.fail_callable = fail_callable or pytest.fail
        self._terminal = None
        self._children = []

    def get_script_path(self):
        """
        Returns the path to the script to run
        """
        if os.path.isabs(self.cli_script_name):
            script_path = self.cli_script_name
        else:
            script_path = compat.which(self.cli_script_name)
        if not os.path.exists(script_path):
            pytest.fail("The CLI script {!r} does not exist".format(script_path))
        return script_path

    def get_base_script_args(self):
        """
        Returns any additional arguments to pass to the CLI script
        """
        return []

    def get_script_args(self):  # pylint: disable=no-self-use
        """
        Returns any additional arguments to pass to the CLI script
        """
        return []

    def init_terminal(self, cmdline, **kwargs):
        """
        Instantiate a terminal with the passed cmdline and kwargs and return it.

        Additionaly, it sets a reference to it in self._terminal and also collects
        an initial listing of child processes which will be used when terminating the
        terminal
        """
        self._terminal = Popen(cmdline, **kwargs)
        for child in psutil.Process(self._terminal.pid).children(recursive=True):
            if child not in self._children:
                self._children.append(child)
        atexit.register(self.terminate)
        return self._terminal

    def terminate(self):
        """
        Terminate the started daemon
        """
        if self._terminal is None:
            return
        log.info("%sStopping %s", self.log_prefix, self.__class__.__name__)
        # Collect any child processes information before terminating the process
        try:
            for child in psutil.Process(self._terminal.pid).children(recursive=True):
                if child not in self._children:
                    self._children.append(child)
        except psutil.NoSuchProcess:
            # The terminal process is gone
            pass

        # Lets log and kill any child processes which salt left behind
        terminate_process(
            pid=self._terminal.pid,
            kill_children=True,
            children=self._children,
            slow_stop=self.slow_stop,
        )
        # This last poll is just to be sure the returncode really get's set on the Popen object.
        self._terminal.poll()
        stdout, stderr = self._terminal.communicate()
        try:
            log_message = "{}Terminated {}.".format(self.log_prefix, self.__class__.__name__)
            if stdout or stderr:
                log_message += (
                    " Process Output:\n>>>>> STDOUT >>>>>\n{}\n<<<<< STDOUT <<<<<\n"
                    ">>>>> STDERR >>>>>\n{}\n<<<<< STDERR <<<<<\n".format(
                        stdout.strip() if stdout else "", stderr.strip() if stderr else ""
                    )
                )
            log.info(log_message)
            return ProcessResult(self._terminal.returncode, stdout, stderr)
        finally:
            self._terminal = None
            self._children = []

    @property
    def pid(self):
        terminal = getattr(self, "_terminal", None)
        if not terminal:
            return
        return terminal.pid

    def __repr__(self):
        return "<{}>".format(self.__class__.__name__)


class FactoryScriptBase(FactoryProcess):
    """
    Base class for CLI scripts
    """

    def __init__(self, *args, **kwargs):
        default_timeout = kwargs.pop("default_timeout", None) or 30
        super(FactoryScriptBase, self).__init__(*args, **kwargs)
        self.default_timeout = default_timeout

    def build_cmdline(self, *args, **kwargs):
        proc_args = [self.get_script_path()] + self.get_base_script_args() + self.get_script_args()
        if sys.platform.startswith("win") and proc_args[0] != sys.executable:
            # Windows needs the python executable to come first
            proc_args.insert(0, sys.executable)
        proc_args += list(args)
        return proc_args

    def run(self, *args, **kwargs):
        """
        Run the given command synchronously
        """
        timeout = kwargs.pop("_timeout", None) or self.default_timeout
        fail_callable = kwargs.pop("_fail_callable", None) or self.fail_callable
        timeout_expire = time.time() + timeout

        # Build the cmdline to pass to the terminal
        proc_args = self.build_cmdline(*args, **kwargs)

        log.info("%sRunning %r in CWD: %s ...", self.log_prefix, proc_args, self.cwd)

        terminal = self.init_terminal(proc_args, cwd=self.cwd, env=self.environ,)
        timmed_out = False
        while True:
            if timeout_expire < time.time():
                timmed_out = True
                break
            if terminal.poll() is not None:
                break
            time.sleep(0.25)

        result = self.terminate()
        if timmed_out:
            fail_callable(
                "{}Failed to run: {}; Error: Timed out after {} seconds!\n"
                ">>>>> STDOUT >>>>>\n{}\n<<<<< STDOUT <<<<<\n"
                ">>>>> STDERR >>>>>\n{}\n<<<<< STDERR <<<<<\n".format(
                    self.log_prefix, proc_args, timeout, result.stdout, result.stderr,
                )
            )

        exitcode = result.exitcode
        stdout, stderr, json_out = self.process_output(
            result.stdout, result.stderr, cli_cmd=proc_args
        )
        return ShellResult(exitcode, stdout, stderr, json_out)

    def process_output(self, stdout, stderr, cli_cmd=None):
        if stdout:
            try:
                json_out = json.loads(stdout)
            except ValueError:
                log.debug(
                    "%sFailed to load JSON from the following output:\n%r", self.log_prefix, stdout
                )
                json_out = None
        else:
            json_out = None
        return stdout, stderr, json_out


class FactoryDaemonScriptBase(FactoryProcess):
    def __init__(self, *args, **kwargs):
        self._process_cli_output_in_thread = kwargs.pop("process_cli_output_in_thread", True)
        super(FactoryDaemonScriptBase, self).__init__(*args, **kwargs)
        self._running = threading.Event()
        self._connectable = threading.Event()
        self._monitor_events_event = threading.Event()

    def is_alive(self):
        """
        Returns true if the process is alive
        """
        return self._running.is_set()

    def get_check_ports(self):  # pylint: disable=no-self-use
        """
        Return a list of ports to check against to ensure the daemon is running
        """
        return []

    def start(self):
        """
        Start the daemon subprocess
        """
        self._monitor_events_event.set()
        log.info("%sStarting DAEMON %s in CWD: %s", self.log_prefix, self.cli_script_name, self.cwd)
        proc_args = [self.get_script_path()] + self.get_base_script_args() + self.get_script_args()

        if sys.platform.startswith("win") and proc_args[0] != sys.executable:
            # Windows needs the python executable to come first
            proc_args.insert(0, sys.executable)

        log.info("%sRunning %r...", self.log_prefix, proc_args)

        self.init_terminal(
            proc_args, env=self.environ, cwd=self.cwd,
        )
        self._running.set()
        self._children.extend(psutil.Process(self.pid).children(recursive=True))
        return True

    def terminate(self):
        """
        Terminate the started daemon
        """
        # Let's get the child processes of the started subprocess
        self._running.clear()
        self._connectable.clear()
        self._monitor_events_event.clear()
        time.sleep(0.0125)
        return super(FactoryDaemonScriptBase, self).terminate()

    def wait_until_running(self, timeout=5):
        """
        Blocking call to wait for the daemon to start listening
        """
        if self._connectable.is_set():
            return True

        expire = time.time() + timeout
        check_ports = self.get_check_ports()
        if check_ports:
            log.debug(
                "%sChecking the following ports to assure running status: %s",
                self.log_prefix,
                check_ports,
            )
        log.debug("%sWaiting %d seconds for running checks to complete.", self.log_prefix, timeout)
        try:
            while True:
                if self._running.is_set() is False:
                    # No longer running, break
                    log.warning("%sNo longer running!", self.log_prefix)
                    break

                if time.time() > expire:
                    # Timeout, break
                    log.debug("%sExpired after %d seconds", self.log_prefix, timeout)
                    break

                if not check_ports:
                    self._connectable.set()
                    break

                for port in set(check_ports):
                    if isinstance(port, int):
                        log.debug(
                            "%sChecking connectable status on port: %s", self.log_prefix, port
                        )
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        conn = sock.connect_ex(("localhost", port))
                        try:
                            if conn == 0:
                                log.debug("%sPort %s is connectable!", self.log_prefix, port)
                                check_ports.remove(port)
                                sock.shutdown(socket.SHUT_RDWR)
                        except socket.error:
                            continue
                        finally:
                            sock.close()
                            del sock
                time.sleep(0.5)
        except KeyboardInterrupt:
            return self._connectable.is_set()
        if self._connectable.is_set():
            log.debug("%sAll ports checked. Running!", self.log_prefix)
            try:
                for child in psutil.Process(self.pid).children(recursive=True):
                    if child not in self._children:
                        self._children.append(child)
            except psutil.NoSuchProcess:
                # The parent process died?!
                pass
        return self._connectable.is_set()

    def __repr__(self):
        try:
            return "<{} id='{id}' role='{__role}'>".format(self.__class__.__name__, **self.config)
        except KeyError:
            return super(FactoryDaemonScriptBase, self).__repr__()


class SaltScriptBase(FactoryScriptBase):
    def get_base_script_args(self):
        script_args = super(SaltScriptBase, self).get_base_script_args()
        if "conf_file" in self.config:
            script_args.extend(["-c", os.path.dirname(self.config["conf_file"])])
        script_args.append("--log-level=quiet")
        script_args.append("--out=json")
        return script_args

    def get_minion_tgt(self, kwargs):
        return kwargs.pop("minion_tgt", None)

    def build_cmdline(self, *args, **kwargs):
        minion_tgt = self._minion_tgt = self.get_minion_tgt(kwargs)
        proc_args = [self.get_script_path()] + self.get_base_script_args() + self.get_script_args()
        if sys.platform.startswith("win") and proc_args[0] != sys.executable:
            # Windows needs the python executable to come first
            proc_args.insert(0, sys.executable)
        if minion_tgt:
            proc_args.append(minion_tgt)
        proc_args += list(args)
        for key in kwargs:
            proc_args.append("{}={}".format(key, kwargs[key]))
        return proc_args


class SaltDaemonScriptBase(FactoryDaemonScriptBase):
    def get_base_script_args(self):
        script_args = super(SaltDaemonScriptBase, self).get_base_script_args()
        if "conf_file" in self.config:
            script_args.extend(["-c", os.path.dirname(self.config["conf_file"])])
        script_args.append("--log-level=quiet")
        return script_args

    def get_check_ports(self):  # pylint: disable=no-self-use
        """
        Return a list of ports to check against to ensure the daemon is running
        """
        pytest_config = self.config.get("pytest-{}".format(self.config["__role"]), {})
        if pytest_config:
            engine_config = pytest_config["engine"]
            if engine_config:
                engine_port = engine_config.get("port")
                if engine_port:
                    return [engine_port]
        return super(SaltDaemonScriptBase, self).get_check_ports()

    def get_check_events(self):
        """
        Return a list of event tags to check against to ensure the daemon is running
        """
        raise NotImplementedError

    def monitor_events(self, monitor_event):
        # Late import
        import salt.utils.event

        if self.config["__role"] == "master":
            config = self.config.copy()
        else:
            config = self.config["pytest-{}".format(self.config["__role"])]["master_config"].copy()
        log.info(
            "Monitoring events for %s(id=%s, sock_dir=%s)",
            self.__class__.__name__,
            config["id"],
            config["sock_dir"],
        )
        try:
            with salt.utils.event.get_master_event(
                config, config["sock_dir"], listen=True, raise_errors=True,
            ) as event_listener:
                while monitor_event.is_set():
                    if self._running.is_set() is False:
                        # No longer running, break
                        log.warning("%sNo longer running!", self.log_prefix)
                        break
                    event = event_listener.get_event(full=True, wait=0.5)
                    if event:
                        log.info("%sMonitored event: %s", self.log_prefix, event)
        except iostream.StreamClosedError:
            pass

    def wait_until_running(
        self, timeout=5, monitor_events=False
    ):  # pylint: disable=arguments-differ
        """
        Blocking call to wait for the daemon to start listening
        """
        if self._connectable.is_set():
            return True

        check_ports = self.get_check_ports()
        if check_ports:
            connectable = super(SaltDaemonScriptBase, self).wait_until_running(timeout=timeout)
            if not connectable:
                # Stop soon
                return connectable
            # Don't yet flag as connectable
            self._connectable.clear()

        # Now check events
        check_events = set(self.get_check_events())
        if not check_events:
            self._connectable.set()
            return self._connectable.is_set()

        if monitor_events:
            self._monitor_events_event.set()
            monitor_events_thread = threading.Thread(
                target=self.monitor_events, args=(self._monitor_events_event,)
            )
            monitor_events_thread.daemon = True
            monitor_events_thread.start()

        expire = time.time() + timeout
        if check_events:
            log.debug(
                "%sChecking the following salt events to assure running status: %s",
                self.log_prefix,
                check_events,
            )
        log.debug(
            "%sWait until running;  Expire: %s;  Timeout: %s;  Current Time: %s",
            self.log_prefix,
            expire,
            timeout,
            time.time(),
        )
        try:
            # Late import
            import salt.utils.event

            pytest_config = self.config["pytest-{}".format(self.config["__role"])]

            stop_sending_events_file = pytest_config["engine"]["stop_sending_events_file"]
            if self.config["__role"] == "master":
                config = self.config.copy()
            else:
                config = pytest_config["master_config"].copy()

            with salt.utils.event.get_master_event(
                config, config["sock_dir"], listen=True, raise_errors=True,
            ) as event_listener:
                while True:
                    if self._running.is_set() is False:
                        # No longer running, break
                        log.warning("%sNo longer running!", self.log_prefix)
                        break

                    if time.time() > expire:
                        # Timeout, break
                        log.debug(
                            "%sExpired at %s(was set to %s)", self.log_prefix, time.time(), expire
                        )
                        break

                    if not check_events:
                        if stop_sending_events_file and os.path.exists(stop_sending_events_file):
                            log.info(
                                "%sRemoving stop_sending_events_file: %s",
                                self.log_prefix,
                                stop_sending_events_file,
                            )
                            os.unlink(stop_sending_events_file)
                        self._connectable.set()
                        break

                    for tag in set(check_events):
                        log.info("%s Waiting for event with tag: %s", self.log_prefix, tag)
                        event = event_listener.get_event(tag=tag, wait=0.5, match_type="startswith")
                        if event and event["tag"].startswith(tag):
                            log.info("%sGot event tag: %s", self.log_prefix, tag)
                            check_events.remove(tag)
        except KeyboardInterrupt:
            # self._monitor_events_event.clear()
            return self._connectable.is_set()
        if self._connectable.is_set():
            log.debug("%sAll events checked. Running!", self.log_prefix)
        # self._monitor_events_event.clear()
        return self._connectable.is_set()


class SaltMaster(SaltDaemonScriptBase):
    """
    Simple subclass to define a salt master daemon
    """

    def get_check_events(self):
        """
        Return a list of event tags to check against to ensure the daemon is running
        """
        return ["pytest/{__role}/{id}/start".format(**self.config)]


class SaltMinion(SaltDaemonScriptBase):
    """
    Simple subclass to define a salt minion daemon
    """

    def get_check_events(self):
        """
        Return a list of event tags to check against to ensure the daemon is running
        """
        # We don't use "salt/{__role}/{id}/start" because those were seen being fired
        # before we even got our engine running
        return ["pytest/{__role}/{id}/start".format(**self.config)]


class SaltSyndic(SaltDaemonScriptBase):
    """
    Simple subclass to define a salt minion daemon
    """

    def get_check_events(self):
        """
        Return a list of event tags to check against to ensure the daemon is running
        """
        return ["salt/{__role}/{id}/start".format(**self.config)]


class SaltCLI(SaltScriptBase):
    """
    Simple subclass to the salt CLI script
    """

    def get_script_args(self):
        """
        Returns any additional arguments to pass to the CLI script
        """
        return ["--log-level=quiet", "--hard-crash"]

    def process_output(self, stdout, stderr, cli_cmd):  # pylint: disable=signature-differs
        if "No minions matched the target. No command was sent, no jid was assigned.\n" in stdout:
            stdout = stdout.split("\n", 1)[1:][0]
        old_stdout = None
        if "--show-jid" in cli_cmd and stdout.startswith("jid: "):
            old_stdout = stdout
            stdout = stdout.split("\n", 1)[-1].strip()
        stdout, stderr, json_out = SaltScriptBase.process_output(self, stdout, stderr, cli_cmd)
        if old_stdout is not None:
            stdout = old_stdout
        if json_out:
            if not isinstance(json_out, dict):
                # A string was most likely loaded, not what we want.
                return stdout, stderr, None
            try:
                return stdout, stderr, json_out[self._minion_tgt]
            except KeyError:
                return stdout, stderr, json_out
        return stdout, stderr, json_out
