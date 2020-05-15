# -*- coding: utf-8 -*-
"""
    saltfactories.utils.processes.bases
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Base process classes
"""
import atexit
import json
import logging
import os
import pprint
import subprocess
import sys
import tempfile
import time
from collections import namedtuple
from operator import itemgetter

import psutil
import pytest

try:
    import salt.utils.path
except ImportError:  # pragma: no cover
    # We need salt to test salt with saltfactories, and, when pytest is rewriting modules for proper assertion
    # reporting, we still haven't had a chance to inject the salt path into sys.modules, so we'll hit this
    # import error, but its safe to pass
    pass

from saltfactories.utils import compat
from saltfactories.utils.processes.helpers import terminate_process
from saltfactories.exceptions import ProcessTimeout

log = logging.getLogger(__name__)


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
        super().__init__(*args, **kwargs)
        self.__stdout = stdout
        self.__stderr = stderr
        compat.weakref.finalize(self, stdout.close)
        compat.weakref.finalize(self, stderr.close)

    def communicate(self, input=None):  # pylint: disable=arguments-differ
        super().communicate(input)
        stdout = stderr = None
        if self.__stdout:
            self.__stdout.flush()
            self.__stdout.seek(0)
            stdout = self.__stdout.read()

            # We want str type on Py3 and Unicode type on Py2
            # pylint: disable=undefined-variable
            stdout = stdout.decode(__salt_system_encoding__)
            # pylint: enable=undefined-variable
        if self.__stderr:
            self.__stderr.flush()
            self.__stderr.seek(0)
            stderr = self.__stderr.read()

            # We want str type on Py3 and Unicode type on Py2
            # pylint: disable=undefined-variable
            stderr = stderr.decode(__salt_system_encoding__)
            # pylint: enable=undefined-variable
        return stdout, stderr


class ProcessResult(namedtuple("ProcessResult", ("exitcode", "stdout", "stderr", "cmdline"))):
    """
    This class serves the purpose of having a common result class which will hold the
    resulting data from a subprocess command.
    """

    __slots__ = ()

    def __new__(cls, exitcode, stdout, stderr, cmdline=None):
        if not isinstance(exitcode, int):
            raise ValueError("'exitcode' needs to be an integer, not '{}'".format(type(exitcode)))
        return super().__new__(cls, exitcode, stdout, stderr, cmdline=cmdline)

    # These are copied from the namedtuple verbose output in order to quiet down PyLint
    exitcode = property(itemgetter(0), doc="ProcessResult exit code property")
    stdout = property(itemgetter(1), doc="ProcessResult stdout property")
    stderr = property(itemgetter(2), doc="ProcessResult stderr property")
    cmdline = property(itemgetter(3), doc="ProcessResult cmdline property")

    def __str__(self):
        message = self.__class__.__name__
        if self.cmdline:
            message += "\n Command Line: {}".format(self.cmdline)
        if self.exitcode is not None:
            message += "\n Exitcode: {}".format(self.exitcode)
        if self.stdout or self.stderr:
            message += "\n Process Output:"
        if self.stdout:
            message += "\n   >>>>> STDOUT >>>>>\n{}\n   <<<<< STDOUT <<<<<".format(self.stdout)
        if self.stderr:
            message += "\n   >>>>> STDERR >>>>>\n{}\n   <<<<< STDERR <<<<<".format(self.stderr)
        return message + "\n"


class ShellResult(namedtuple("ShellResult", ("exitcode", "stdout", "stderr", "json", "cmdline"))):
    """
    This class serves the purpose of having a common result class which will hold the
    resulting data from a subprocess command.
    """

    __slots__ = ()

    def __new__(cls, exitcode, stdout, stderr, json=None, cmdline=None):
        if not isinstance(exitcode, int):
            raise ValueError("'exitcode' needs to be an integer, not '{}'".format(type(exitcode)))
        return super().__new__(cls, exitcode, stdout, stderr, json=json, cmdline=cmdline)

    # These are copied from the namedtuple verbose output in order to quiet down PyLint
    exitcode = property(itemgetter(0), doc="ShellResult exit code property")
    stdout = property(itemgetter(1), doc="ShellResult stdout property")
    stderr = property(itemgetter(2), doc="ShellResult stderr property")
    json = property(itemgetter(3), doc="ShellResult stdout JSON decoded, when parseable.")
    cmdline = property(itemgetter(4), doc="ShellResult cmdline property")

    def __str__(self):
        message = self.__class__.__name__
        if self.cmdline:
            message += "\n Command Line: {}".format(self.cmdline)
        if self.exitcode is not None:
            message += "\n Exitcode: {}".format(self.exitcode)
        if self.stdout or self.stderr:
            message += "\n Process Output:"
        if self.stdout:
            message += "\n   >>>>> STDOUT >>>>>\n{}\n   <<<<< STDOUT <<<<<".format(self.stdout)
        if self.stderr:
            message += "\n   >>>>> STDERR >>>>>\n{}\n   <<<<< STDERR <<<<<".format(self.stderr)
        if self.json:
            message += "\n JSON Object:\n"
            message += "".join("  {}".format(line) for line in pprint.pformat(self.json))
        return message + "\n"

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
        self, cli_script_name, slow_stop=True, environ=None, cwd=None, base_script_args=None,
    ):
        """

        Args:
            cli_script_name(str):
                This is the string containing the name of the binary to call on the subprocess, either the
                full path to it, or the basename. In case of the basename, the directory containing the
                basename must be in your ``$PATH`` variable.
            slow_stop(bool):
                Wether to terminate the processes by sending a :py:attr:`SIGTERM` signal or by calling
                :py:meth:`~subprocess.Popen.terminate` on the sub-procecess.
                When code coverage is enabled, one will want `slow_stop` set to `True` so that coverage data
                can be written down to disk.
            environ(dict):
                A dictionary of `key`, `value` pairs to add to the environment.
            cwd (str):
                The path to the current working directory
            base_script_args(list or tuple):
                An list or tuple iterable of the base arguments to use when building the command line to
                launch the process
        """
        self.cli_script_name = cli_script_name
        self.slow_stop = slow_stop
        self.environ = environ or os.environ.copy()
        self.cwd = cwd or os.getcwd()
        self._terminal = None
        self._terminal_result = None
        self._terminal_timeout = None
        self._children = []
        self._base_script_args = base_script_args

    def get_display_name(self):
        """
        Returns a name to show when process stats reports are enabled
        """
        return self.cli_script_name

    def get_log_prefix(self):
        """
        Returns the log prefix that shall be used for a salt daemon forwarding log records.
        It is also used by :py:func:`start_daemon` when starting the daemon subprocess.
        """
        return "[{}] ".format(self.cli_script_name)

    def get_script_path(self):
        """
        Returns the path to the script to run
        """
        if os.path.isabs(self.cli_script_name):
            script_path = self.cli_script_name
        else:
            script_path = salt.utils.path.which(self.cli_script_name)
        if not os.path.exists(script_path):
            pytest.fail("The CLI script {!r} does not exist".format(script_path))
        return script_path

    def get_base_script_args(self):
        """
        Returns any additional arguments to pass to the CLI script
        """
        if self._base_script_args:
            return list(self._base_script_args)
        return []

    def get_script_args(self):  # pylint: disable=no-self-use
        """
        Returns any additional arguments to pass to the CLI script
        """
        return []

    def build_cmdline(self, *args, **kwargs):
        return (
            [self.get_script_path()]
            + self.get_base_script_args()
            + self.get_script_args()
            + list(args)
        )

    def init_terminal(self, cmdline, **kwargs):
        """
        Instantiate a terminal with the passed cmdline and kwargs and return it.

        Additionaly, it sets a reference to it in self._terminal and also collects
        an initial listing of child processes which will be used when terminating the
        terminal
        """
        self._terminal = Popen(cmdline, **kwargs)
        # A little sleep to allow the subprocess to start
        time.sleep(0.125)
        try:
            for child in psutil.Process(self._terminal.pid).children(recursive=True):
                if child not in self._children:
                    self._children.append(child)
        except psutil.NoSuchProcess:
            # The terminal process is gone
            pass
        atexit.register(self.terminate)
        return self._terminal

    def terminate(self):
        """
        Terminate the started daemon
        """
        if self._terminal is None:
            return self._terminal_result
        log.info("%sStopping %s", self.get_log_prefix(), self.__class__.__name__)
        # Collect any child processes information before terminating the process
        try:
            for child in psutil.Process(self._terminal.pid).children(recursive=True):
                if child not in self._children:
                    self._children.append(child)
        except psutil.NoSuchProcess:
            # The terminal process is gone
            pass

        # poll the terminal before trying to terminate it, running or not, so that
        # the right returncode is set on the popen object
        self._terminal.poll()
        # Lets log and kill any child processes which salt left behind
        terminate_process(
            pid=self._terminal.pid,
            kill_children=True,
            children=self._children,
            slow_stop=self.slow_stop,
        )
        stdout, stderr = self._terminal.communicate()
        try:
            log_message = "{}Terminated {}.".format(self.get_log_prefix(), self.__class__.__name__)
            if stdout or stderr:
                log_message += " Process Output:"
                if stdout:
                    log_message += "\n>>>>> STDOUT >>>>>\n{}\n<<<<< STDOUT <<<<<".format(
                        stdout.strip()
                    )
                if stderr:
                    log_message += "\n>>>>> STDERR >>>>>\n{}\n<<<<< STDERR <<<<<".format(
                        stderr.strip()
                    )
                log_message += "\n"
            log.info(log_message)
            self._terminal_result = ProcessResult(
                self._terminal.returncode, stdout, stderr, cmdline=self._terminal.args
            )
            return self._terminal_result
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
        return "<{} display_name='{}'>".format(self.__class__.__name__, self.get_display_name())


class FactoryScriptBase(FactoryProcess):
    """
    Base class for CLI scripts
    """

    def __init__(self, *args, **kwargs):
        """
        Base class for non daemonic CLI processes

        Check base class(es) for additional supported parameters

        Args:
            default_timeout(int):
                The maximum ammount of seconds that a script should run
        """
        default_timeout = kwargs.pop("default_timeout", None)
        super().__init__(*args, **kwargs)
        if default_timeout is None:
            if not sys.platform.startswith("win"):
                default_timeout = 30
            else:
                # Windows is just slower.
                default_timeout = 120
        self.default_timeout = default_timeout
        self._terminal_timeout_set_explicitly = False

    def run(self, *args, **kwargs):
        """
        Run the given command synchronously
        """
        start_time = time.time()
        timeout = kwargs.pop("_timeout", None)

        # Build the cmdline to pass to the terminal
        # We set the _terminal_timeout attribute while calling build_cmdline in case it needs
        # access to that information to build the command line
        self._terminal_timeout = timeout or self.default_timeout
        self._terminal_timeout_set_explicitly = timeout is not None
        cmdline = self.build_cmdline(*args, **kwargs)
        timeout_expire = time.time() + self._terminal_timeout

        log.info("%sRunning %r in CWD: %s ...", self.get_log_prefix(), cmdline, self.cwd)

        terminal = self.init_terminal(cmdline, cwd=self.cwd, env=self.environ,)
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
            raise ProcessTimeout(
                "{}Failed to run: {}; Error: Timed out after {:.2f} seconds!".format(
                    self.get_log_prefix(), cmdline, time.time() - start_time
                ),
                stdout=result.stdout,
                stderr=result.stderr,
                cmdline=cmdline,
                exitcode=result.exitcode,
            )

        exitcode = result.exitcode
        stdout, stderr, json_out = self.process_output(
            result.stdout, result.stderr, cmdline=cmdline
        )
        log.info(
            "%sCompleted %r in CWD: %s after %.2f seconds",
            self.get_log_prefix(),
            cmdline,
            self.cwd,
            time.time() - start_time,
        )
        return ShellResult(exitcode, stdout, stderr, json=json_out, cmdline=cmdline)

    def process_output(self, stdout, stderr, cmdline=None):
        if stdout:
            try:
                json_out = json.loads(stdout)
            except ValueError:
                log.debug(
                    "%sFailed to load JSON from the following output:\n%r",
                    self.get_log_prefix(),
                    stdout,
                )
                json_out = None
        else:
            json_out = None
        return stdout, stderr, json_out


class FactoryPythonScriptBase(FactoryScriptBase):
    def __init__(self, *args, **kwargs):
        """
        Base class for python scripts based CLI processes

        Check base class(es) for additional supported parameters

        Args:
            python_executable(str):
                The path to the python executable to use
        """
        python_executable = kwargs.pop("python_executable", None)
        super().__init__(*args, **kwargs)
        self.python_executable = python_executable or sys.executable
        # We really do not want buffered output
        self.environ.setdefault(str("PYTHONUNBUFFERED"), str("1"))
        # Don't write .pyc files or create them in __pycache__ directories
        self.environ.setdefault(str("PYTHONDONTWRITEBYTECODE"), str("1"))

    def build_cmdline(self, *args, **kwargs):
        cmdline = super().build_cmdline(*args, **kwargs)
        if cmdline[0] != self.python_executable:
            cmdline.insert(0, self.python_executable)
        return cmdline


class FactoryDaemonScriptBase(FactoryProcess):
    def is_alive(self):
        """
        Returns true if the process is alive
        """
        terminal = getattr(self, "_terminal", None)
        if not terminal:
            return False
        return terminal.poll() is None

    def get_check_ports(self):  # pylint: disable=no-self-use
        """
        Return a list of ports to check against to ensure the daemon is running
        """
        return []

    def start(self):
        """
        Start the daemon subprocess
        """
        log.info(
            "%sStarting DAEMON %s in CWD: %s", self.get_log_prefix(), self.cli_script_name, self.cwd
        )
        cmdline = self.build_cmdline()

        log.info("%sRunning %r...", self.get_log_prefix(), cmdline)

        self.init_terminal(
            cmdline, env=self.environ, cwd=self.cwd,
        )
        self._children.extend(psutil.Process(self.pid).children(recursive=True))
        return True
