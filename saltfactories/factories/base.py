"""
..
    PYTEST_DONT_REWRITE


saltfactories.factories.base
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Factories base classes
"""
import atexit
import json
import logging
import os
import sys
import time

import attr
import psutil
import pytest
import salt.utils.path

from saltfactories.exceptions import FactoryTimeout
from saltfactories.utils.processes import Popen
from saltfactories.utils.processes import ProcessResult
from saltfactories.utils.processes import ShellResult
from saltfactories.utils.processes.helpers import terminate_process

log = logging.getLogger(__name__)


@attr.s(kw_only=True)
class Factory:
    """
    Base factory class

    Args:
        display_name(str):
            Human readable name for the factory
        environ(dict):
            A dictionary of `key`, `value` pairs to add to the environment.
        cwd (str):
            The path to the current working directory
    """

    display_name = attr.ib(default=None)
    cwd = attr.ib(default=None)
    environ = attr.ib(repr=False, default=None)

    def __attrs_post_init__(self):
        if self.environ is None:
            self.environ = os.environ.copy()
        if self.cwd is None:
            self.cwd = os.getcwd()

    def get_display_name(self):
        """
        Returns a human readable name for the factory
        """
        if self.display_name:
            return "{}({})".format(self.__class__.__name__, self.display_name)
        return self.__class__.__name__


@attr.s(kw_only=True)
class SubprocessFactoryBase(Factory):
    """
    Base CLI script/binary class

    Args:
        cli_script_name(str):
            This is the string containing the name of the binary to call on the subprocess, either the
            full path to it, or the basename. In case of the basename, the directory containing the
            basename must be in your ``$PATH`` variable.
        base_script_args(list or tuple):
            An list or tuple iterable of the base arguments to use when building the command line to
            launch the process
        slow_stop(bool):
            Whether to terminate the processes by sending a :py:attr:`SIGTERM` signal or by calling
            :py:meth:`~subprocess.Popen.terminate` on the sub-process.
            When code coverage is enabled, one will want `slow_stop` set to `True` so that coverage data
            can be written down to disk.
    """

    cli_script_name = attr.ib()
    base_script_args = attr.ib(default=None)
    slow_stop = attr.ib(default=True)

    _terminal = attr.ib(repr=False, init=False, default=None)
    _terminal_result = attr.ib(repr=False, init=False, default=None)
    _terminal_timeout = attr.ib(repr=False, init=False, default=None)
    _children = attr.ib(repr=False, init=False, default=attr.Factory(list))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.base_script_args is None:
            self.base_script_args = []

    def get_display_name(self):
        """
        Returns a human readable name for the factory
        """
        return self.display_name or self.cli_script_name

    def get_script_path(self):
        """
        Returns the path to the script to run
        """
        if os.path.isabs(self.cli_script_name):
            script_path = self.cli_script_name
        else:
            script_path = salt.utils.path.which(self.cli_script_name)
        if not script_path or not os.path.exists(script_path):
            pytest.fail("The CLI script {!r} does not exist".format(script_path))
        return script_path

    def get_base_script_args(self):
        """
        Returns any additional arguments to pass to the CLI script
        """
        return list(self.base_script_args)

    def get_script_args(self):  # pylint: disable=no-self-use
        """
        Returns any additional arguments to pass to the CLI script
        """
        return []

    def build_cmdline(self, *args):
        """
        Construct a list of arguments to use when starting the subprocess

        Args:
            args:
                Additional arguments to use when starting the subprocess
        """
        return (
            [self.get_script_path()]
            + self.get_base_script_args()
            + self.get_script_args()
            + list(args)
        )

    def init_terminal(self, cmdline, **kwargs):
        """
        Instantiate a terminal with the passed cmdline and kwargs and return it.

        Additionally, it sets a reference to it in self._terminal and also collects
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

    def is_running(self):
        """
        Returns true if the sub-process is alive
        """
        if not self._terminal:
            return False
        return self._terminal.poll() is None

    def terminate(self):
        """
        Terminate the started daemon
        """
        if self._terminal is None:
            return self._terminal_result
        log.info("Stopping %s", self)
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
        # Lets log and kill any child processes left behind
        terminate_process(
            pid=self._terminal.pid,
            kill_children=True,
            children=self._children,
            slow_stop=self.slow_stop,
        )
        stdout, stderr = self._terminal.communicate()
        try:
            log_message = "Terminated {}.".format(self)
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
            self._terminal_timeout = None
            self._children = []

    @property
    def pid(self):
        if not self._terminal:
            return
        return self._terminal.pid

    def _run(self, *args, **kwargs):
        """
        Run the given command synchronously
        """
        cmdline = self.build_cmdline(*args, **kwargs)

        log.info("%s is running %r in CWD: %s ...", self, cmdline, self.cwd)

        terminal = self.init_terminal(cmdline, cwd=self.cwd, env=self.environ)
        try:
            self._children.extend(psutil.Process(self.pid).children(recursive=True))
        except psutil.NoSuchProcess:
            # Process already died?!
            pass
        return terminal


@attr.s(kw_only=True)
class ProcessFactory(SubprocessFactoryBase):
    """
    Base process factory

    Args:
        default_timeout(int):
            The maximum amount of seconds that a script should run
    """

    default_timeout = attr.ib()
    _terminal_timeout_set_explicitly = attr.ib(repr=False, init=False, default=False)

    @default_timeout.default
    def _set_default_timeout(self):
        if not sys.platform.startswith(("win", "darwin")):
            return 30
        # Windows and macOS are just slower.
        return 120

    def run(self, *args, _timeout=None, **kwargs):
        """
        Run the given command synchronously
        """
        start_time = time.time()
        # Build the cmdline to pass to the terminal
        # We set the _terminal_timeout attribute while calling build_cmdline in case it needs
        # access to that information to build the command line
        self._terminal_timeout = _timeout or self.default_timeout
        self._terminal_timeout_set_explicitly = _timeout is not None
        timeout_expire = time.time() + self._terminal_timeout
        running = self._run(*args, **kwargs)

        timmed_out = False
        while True:
            if timeout_expire < time.time():
                timmed_out = True
                break
            if self._terminal.poll() is not None:
                break
            time.sleep(0.25)

        result = self.terminate()
        if timmed_out:
            raise FactoryTimeout(
                "{} Failed to run: {}; Error: Timed out after {:.2f} seconds!".format(
                    self, result.cmdline, time.time() - start_time
                ),
                stdout=result.stdout,
                stderr=result.stderr,
                cmdline=result.cmdline,
                exitcode=result.exitcode,
            )

        cmdline = result.cmdline
        exitcode = result.exitcode
        stdout, stderr, json_out = self.process_output(
            result.stdout, result.stderr, cmdline=cmdline
        )
        log.info(
            "%s completed %r in CWD: %s after %.2f seconds",
            self,
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
                    "%s failed to load JSON from the following output:\n%r", self, stdout,
                )
                json_out = None
        else:
            json_out = None
        return stdout, stderr, json_out


@attr.s(kw_only=True)
class DaemonFactory(SubprocessFactoryBase):
    """
    Base daemon factory
    """

    check_ports = attr.ib(default=None)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.check_ports and not isinstance(self.check_ports, (list, tuple)):
            self.check_ports = [self.check_ports]

    def get_check_ports(self):  # pylint: disable=no-self-use
        """
        Return a list of ports to check against to ensure the daemon is running
        """
        return self.check_ports or []

    def start(self):
        """
        Start the daemon
        """
        self._run()
        return self.is_running()


@attr.s(kw_only=True)
class SaltFactory:
    """
    Base factory for salt cli's and daemon's

    Args:
        config(dict):
            The Salt config dictionary
        python_executable(str):
            The path to the python executable to use
    """

    config = attr.ib(repr=False)
    config_dir = attr.ib(init=False, default=None)
    config_file = attr.ib(init=False, default=None)
    python_executable = attr.ib(default=None)
    display_name = attr.ib(init=False, default=None)

    def __attrs_post_init__(self):
        if self.python_executable is None:
            self.python_executable = sys.executable
        # We really do not want buffered output
        self.environ.setdefault("PYTHONUNBUFFERED", "1")
        # Don't write .pyc files or create them in __pycache__ directories
        self.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
        self.config_file = self.config["conf_file"]
        self.config_dir = os.path.dirname(self.config_file)

    def get_display_name(self):
        """
        Returns a human readable name for the factory
        """
        if self.display_name is None:
            self.display_name = self.cli_script_name
        return self.display_name


@attr.s(kw_only=True)
class SaltCliFactory(ProcessFactory, SaltFactory):
    """
    Base factory for salt cli's

    Args:
        hard_crash(bool):
            Pass ``--hard-crash`` to Salt's CLI's
    """

    hard_crash = attr.ib(repr=False, default=False)
    # Override the following to default to non-mandatory and to None
    display_name = attr.ib(init=False, default=None)
    _minion_tgt = attr.ib(repr=False, init=False, default=None)

    __cli_timeout_supported__ = attr.ib(repr=False, init=False, default=False)
    __cli_log_level_supported__ = attr.ib(repr=False, init=False, default=True)
    # Override the following to default to non-mandatory and to None
    display_name = attr.ib(init=False, default=None)

    def __attrs_post_init__(self):
        ProcessFactory.__attrs_post_init__(self)
        SaltFactory.__attrs_post_init__(self)

    def get_script_args(self):
        """
        Returns any additional arguments to pass to the CLI script
        """
        if not self.hard_crash:
            return super().get_script_args()
        return ["--hard-crash"]

    def get_minion_tgt(self, minion_tgt=None):
        return minion_tgt

    def build_cmdline(self, *args, minion_tgt=None, **kwargs):  # pylint: disable=arguments-differ
        """
        Construct a list of arguments to use when starting the subprocess

        Args:
            args:
                Additional arguments to use when starting the subprocess
            kwargs:
                Keyword arguments will be converted into ``key=value`` pairs to be consumed by the salt CLI's
            minion_tgt(str):
                The minion ID to target
        """
        log.debug(
            "Building cmdline. Minion target: %s; Input args: %s; Input kwargs: %s;",
            minion_tgt,
            args,
            kwargs,
        )
        minion_tgt = self._minion_tgt = self.get_minion_tgt(minion_tgt=minion_tgt)
        cmdline = []

        args = list(args)

        # Handle the config directory flag
        for arg in args:
            if arg.startswith("--config-dir="):
                break
            if arg in ("-c", "--config-dir"):
                break
        else:
            cmdline.append("--config-dir={}".format(self.config_dir))

        # Handle the timeout CLI flag, if supported
        if self.__cli_timeout_supported__:
            salt_cli_timeout_next = False
            for arg in args:
                if arg.startswith("--timeout="):
                    # Let's actually change the _terminal_timeout value which is used to
                    # calculate when the run() method should actually timeout
                    if self._terminal_timeout_set_explicitly is False:
                        salt_cli_timeout = arg.split("--timeout=")[-1]
                        try:
                            self._terminal_timeout = int(salt_cli_timeout) + 5
                        except ValueError:
                            # Not a number? Let salt do it's error handling
                            pass
                    break
                if salt_cli_timeout_next:
                    if self._terminal_timeout_set_explicitly is False:
                        try:
                            self._terminal_timeout = int(arg) + 5
                        except ValueError:
                            # Not a number? Let salt do it's error handling
                            pass
                    break
                if arg == "-t" or arg.startswith("--timeout"):
                    salt_cli_timeout_next = True
                    continue
            else:
                salt_cli_timeout = self._terminal_timeout
                if salt_cli_timeout and self._terminal_timeout_set_explicitly is False:
                    # Shave off a few seconds so that the salt command times out before the terminal does
                    salt_cli_timeout -= 5
                if salt_cli_timeout:
                    # If it's still a positive number, add it to the salt command CLI flags
                    cmdline.append("--timeout={}".format(salt_cli_timeout))

        # Handle the output flag
        for arg in args:
            if arg in ("--out", "--output"):
                break
            if arg.startswith(("--out=", "--output=")):
                break
        else:
            # No output was passed, the default output is JSON
            cmdline.append("--out=json")

        if self.__cli_log_level_supported__:
            # Handle the logging flag
            for arg in args:
                if arg in ("-l", "--log-level"):
                    break
                if arg.startswith("--log-level="):
                    break
            else:
                # Default to being quiet on console output
                cmdline.append("--log-level=quiet")

        if minion_tgt:
            cmdline.append(minion_tgt)

        # Add the remaining args
        cmdline.extend(args)

        # Keyword arguments get passed as KEY=VALUE pairs to the CLI
        for key in kwargs:
            value = kwargs[key]
            if not isinstance(value, str):
                value = json.dumps(value)
            cmdline.append("{}={}".format(key, value))
        cmdline = super().build_cmdline(*cmdline)
        if self.python_executable:
            if cmdline[0] != self.python_executable:
                cmdline.insert(0, self.python_executable)
        log.debug("Built cmdline: %s", cmdline)
        return cmdline

    def process_output(self, stdout, stderr, cmdline=None):
        stdout, stderr, json_out = super().process_output(stdout, stderr, cmdline=cmdline)
        if json_out and isinstance(json_out, str) and "--out=json" in cmdline:
            # Sometimes the parsed JSON is just a string, for example:
            #  OUTPUT: '"The salt master could not be contacted. Is master running?"\n'
            #  LOADED JSON: 'The salt master could not be contacted. Is master running?'
            #
            # In this case, we assign the loaded JSON to stdout and reset json_out
            stdout = json_out
            json_out = None
        if json_out and self._minion_tgt:
            try:
                json_out = json_out[self._minion_tgt]
            except KeyError:
                pass
        return stdout, stderr, json_out


@attr.s(kw_only=True)
class SaltDaemonFactory(DaemonFactory, SaltFactory):
    """
    Base factory for salt daemon's
    """

    _display_name = attr.ib(repr=False, init=False, default=None)
    # Override the following to default to non-mandatory and to None
    display_name = attr.ib(init=False, default=None)

    def __attrs_post_init__(self):
        DaemonFactory.__attrs_post_init__(self)
        SaltFactory.__attrs_post_init__(self)
        self.base_script_args.append("--config-dir={}".format(self.config_dir))
        self.base_script_args.append("--log-level=quiet")
        if self.display_name is None:
            self.display_name = self.config["id"]

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        raise NotImplementedError

    def build_cmdline(self, *args):
        cmdline = super().build_cmdline(*args)
        if self.python_executable:
            if cmdline[0] != self.python_executable:
                cmdline.insert(0, self.python_executable)
        return cmdline
