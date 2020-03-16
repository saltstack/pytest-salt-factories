# -*- coding: utf-8 -*-
"""
    saltfactories.utils.processes.bases
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Base process classes
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import atexit
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from collections import namedtuple
from operator import itemgetter

import psutil
import pytest
import six

try:
    import salt.utils.path
except ImportError:
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
        super(Popen, self).__init__(*args, **kwargs)
        self.__stdout = stdout
        self.__stderr = stderr
        compat.weakref.finalize(self, stdout.close)
        compat.weakref.finalize(self, stderr.close)

    def communicate(self, input=None):  # pylint: disable=arguments-differ
        super(Popen, self).communicate(input)
        stdout = stderr = None
        if self.__stdout:
            self.__stdout.flush()
            self.__stdout.seek(0)
            stdout = self.__stdout.read()

            if six.PY3:
                # pylint: disable=undefined-variable
                stdout = stdout.decode(__salt_system_encoding__)
                # pylint: enable=undefined-variable
        if self.__stderr:
            self.__stderr.flush()
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
        self, cli_script_name, slow_stop=True, environ=None, cwd=None, base_script_args=None,
    ):
        self.cli_script_name = cli_script_name
        self.slow_stop = slow_stop
        self.environ = environ or os.environ.copy()
        self.cwd = cwd or os.getcwd()
        self._terminal = None
        self._terminal_result = None
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
            return self._terminal_result
        # Allow some time to get all output from process
        time.sleep(0.125)
        log.info("%sStopping %s", self.get_log_prefix(), self.__class__.__name__)
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
            self._terminal_result = ProcessResult(self._terminal.returncode, stdout, stderr)
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
        default_timeout = kwargs.pop("default_timeout", None) or 30
        super(FactoryScriptBase, self).__init__(*args, **kwargs)
        self.default_timeout = default_timeout

    def run(self, *args, **kwargs):
        """
        Run the given command synchronously
        """
        timeout = kwargs.pop("_timeout", None) or self.default_timeout
        timeout_expire = time.time() + timeout

        # Build the cmdline to pass to the terminal
        proc_args = self.build_cmdline(*args, **kwargs)

        log.info("%sRunning %r in CWD: %s ...", self.get_log_prefix(), proc_args, self.cwd)

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
            raise ProcessTimeout(
                "{}Failed to run: {}; Error: Timed out after {} seconds!".format(
                    self.get_log_prefix(), proc_args, timeout
                ),
                stdout=result.stdout,
                stderr=result.stderr,
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
        python_executable = kwargs.pop("python_executable", None)
        super(FactoryPythonScriptBase, self).__init__(*args, **kwargs)
        self.python_executable = python_executable or sys.executable
        # We really do not want buffered output
        self.environ.setdefault(str("PYTHONUNBUFFERED"), str("1"))
        # Don't write .pyc files or create them in __pycache__ directories
        self.environ.setdefault(str("PYTHONDONTWRITEBYTECODE"), str("1"))

    def build_cmdline(self, *args, **kwargs):
        proc_args = super(FactoryPythonScriptBase, self).build_cmdline(*args, **kwargs)
        if proc_args[0] != self.python_executable:
            proc_args.insert(0, self.python_executable)
        return proc_args


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
