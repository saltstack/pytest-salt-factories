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
import pprint
import sys
import time

import attr
import psutil
import pytest
import salt.utils.files
import salt.utils.path
import salt.utils.verify
import salt.utils.yaml

from saltfactories.exceptions import FactoryNotStarted
from saltfactories.exceptions import FactoryTimeout
from saltfactories.utils import ports
from saltfactories.utils import running_username
from saltfactories.utils.processes import Popen
from saltfactories.utils.processes import ProcessResult
from saltfactories.utils.processes import ShellResult
from saltfactories.utils.processes import terminate_process

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
        # Reset the previous _terminal_result if set
        self._terminal_result = None
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
        atexit.unregister(self.terminate)
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
    factories_manager = attr.ib(repr=False, hash=False, default=None)
    start_timeout = attr.ib(repr=False)
    max_start_attempts = attr.ib(repr=False, default=3)
    before_start_callbacks = attr.ib(repr=False, hash=False, default=attr.Factory(list))
    before_terminate_callbacks = attr.ib(repr=False, hash=False, default=attr.Factory(list))
    after_start_callbacks = attr.ib(repr=False, hash=False, default=attr.Factory(list))
    after_terminate_callbacks = attr.ib(repr=False, hash=False, default=attr.Factory(list))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.check_ports and not isinstance(self.check_ports, (list, tuple)):
            self.check_ports = [self.check_ports]

    def register_before_start_callback(self, callback, *args, **kwargs):
        self.before_start_callbacks.append((callback, args, kwargs))

    def register_before_terminate_callback(self, callback, *args, **kwargs):
        self.before_terminate_callbacks.append((callback, args, kwargs))

    def register_after_start_callback(self, callback, *args, **kwargs):
        self.after_start_callbacks.append((callback, args, kwargs))

    def register_after_terminate_callback(self, callback, *args, **kwargs):
        self.after_terminate_callbacks.append((callback, args, kwargs))

    def get_check_ports(self):
        """
        Return a list of ports to check against to ensure the daemon is running
        """
        return self.check_ports or []

    def _format_callback(self, callback, args, kwargs):
        callback_str = "{}(".format(callback.__name__)
        if args:
            callback_str += ", ".join(args)
        if kwargs:
            callback_str += ", ".join(["{}={!r}".format(k, v) for (k, v) in kwargs.items()])
        callback_str += ")"
        return callback_str

    def start(self, max_start_attempts=None, start_timeout=None):
        """
        Start the daemon
        """
        if self.is_running():
            log.warning("%s is already running.", self)
            return True
        process_running = False
        for callback, args, kwargs in self.before_start_callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as exc:  # pylint: disable=broad-except
                log.info(
                    "Exception raised when running %s: %s",
                    self._format_callback(callback, args, kwargs),
                    exc,
                    exc_info=True,
                )
        start_time = time.time()
        start_attempts = max_start_attempts or self.max_start_attempts
        current_attempt = 0
        while current_attempt <= start_attempts:
            current_attempt += 1
            if process_running:
                break
            log.info("Starting %s. Attempt: %d of %d", self, current_attempt, start_attempts)
            current_start_time = time.time()
            start_running_timeout = current_start_time + (start_timeout or self.start_timeout)
            self._run()
            if not self.is_running():
                # A little breathe time to allow the process to start if not started already
                time.sleep(0.5)
            while time.time() <= start_running_timeout:
                if not self.is_running():
                    break
                if self.run_start_checks(current_start_time, start_running_timeout) is False:
                    time.sleep(1)
                    continue
                log.info(
                    "The %s factory is running after %d attempts. Took %1.2f seconds",
                    self,
                    current_attempt,
                    time.time() - start_time,
                )
                process_running = True
                break
            else:
                # The factory failed to confirm it's running status
                self.terminate()
        if process_running:
            for callback, args, kwargs in self.after_start_callbacks:
                try:
                    callback(*args, **kwargs)
                except Exception as exc:  # pylint: disable=broad-except
                    log.info(
                        "Exception raised when running %s: %s",
                        self._format_callback(callback, args, kwargs),
                        exc,
                        exc_info=True,
                    )
            if self.factories_manager and self.factories_manager.stats_processes is not None:
                self.factories_manager.stats_processes[self.get_display_name()] = psutil.Process(
                    self.pid
                )
            return process_running
        result = self.terminate()
        raise FactoryNotStarted(
            "The {} factory has failed to confirm running status after {} attempts, which "
            "took {:.2f} seconds({:.2f} seconds each)".format(
                self,
                current_attempt - 1,
                time.time() - start_time,
                start_timeout or self.start_timeout,
            ),
            stdout=result.stdout,
            stderr=result.stderr,
            exitcode=result.exitcode,
        )

    def started(self, max_start_attempts=None, start_timeout=None):
        """
        Start the daemon and return it's instance so it can be used as a context manager
        """
        self.start(max_start_attempts=max_start_attempts, start_timeout=start_timeout)
        return self

    def terminate(self):
        if self._terminal_result is not None:
            # This factory has already been terminated
            return self._terminal_result
        for callback, args, kwargs in self.before_terminate_callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as exc:  # pylint: disable=broad-except
                log.info(
                    "Exception raised when running %s: %s",
                    self._format_callback(callback, args, kwargs),
                    exc,
                    exc_info=True,
                )
        try:
            return super().terminate()
        finally:
            for callback, args, kwargs in self.after_terminate_callbacks:
                try:
                    callback(*args, **kwargs)
                except Exception as exc:  # pylint: disable=broad-except
                    log.info(
                        "Exception raised when running %s: %s",
                        self._format_callback(callback, args, kwargs),
                        exc,
                        exc_info=True,
                    )

    def run_start_checks(self, started_at, timeout_at):
        check_ports = set(self.get_check_ports())
        if not check_ports:
            return True
        checks_start_time = time.time()
        while time.time() <= timeout_at:
            if not self.is_running():
                log.info("%s is no longer running", self)
                return False
            if not check_ports:
                break
            check_ports -= ports.get_connectable_ports(check_ports)
        else:
            log.error("Failed to check ports after %1.2f seconds", time.time() - checks_start_time)
            return False
        return True

    def __enter__(self):
        if not self.is_running():
            raise RuntimeError(
                "Factory not yet started. Perhaps you're after something like:\n\n"
                "with {}.started() as factory:\n"
                "    yield factory".format(self.__class__.__name__)
            )
        return self

    def __exit__(self, *exc):
        return self.terminate()


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

    id = attr.ib(default=None, init=False)
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
        self.id = self.config["id"]

    def get_display_name(self):
        """
        Returns a human readable name for the factory
        """
        if self.display_name is None:
            self.display_name = self.cli_script_name
        return self.display_name


@attr.s(kw_only=True)
class SaltCliFactory(SaltFactory, ProcessFactory):
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
    __cli_output_supported__ = attr.ib(repr=False, init=False, default=True)
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
        if self.__cli_output_supported__:
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
        if (
            self.__cli_output_supported__
            and json_out
            and isinstance(json_out, str)
            and "--out=json" in cmdline
        ):
            # Sometimes the parsed JSON is just a string, for example:
            #  OUTPUT: '"The salt master could not be contacted. Is master running?"\n'
            #  LOADED JSON: 'The salt master could not be contacted. Is master running?'
            #
            # In this case, we assign the loaded JSON to stdout and reset json_out
            stdout = json_out
            json_out = None
        if self.__cli_output_supported__ and json_out and self._minion_tgt:
            try:
                json_out = json_out[self._minion_tgt]
            except KeyError:
                pass
        return stdout, stderr, json_out


@attr.s(kw_only=True)
class SaltDaemonFactory(SaltFactory, DaemonFactory):
    """
    Base factory for salt daemon's
    """

    display_name = attr.ib(init=False, default=None)
    event_listener = attr.ib(repr=False, default=None)
    started_at = attr.ib(repr=False, default=None)

    def __attrs_post_init__(self):
        DaemonFactory.__attrs_post_init__(self)
        SaltFactory.__attrs_post_init__(self)
        self.base_script_args.append("--config-dir={}".format(self.config_dir))
        self.base_script_args.append("--log-level=quiet")
        if self.display_name is None:
            self.display_name = self.id

    @classmethod
    def configure(
        cls,
        factories_manager,
        daemon_id,
        root_dir=None,
        config_defaults=None,
        config_overrides=None,
        **configure_kwargs
    ):
        return cls._configure(
            factories_manager,
            daemon_id,
            root_dir=root_dir,
            config_defaults=config_defaults,
            config_overrides=config_overrides,
            **configure_kwargs
        )

    @classmethod
    def _configure(
        cls,
        factories_manager,
        daemon_id,
        root_dir=None,
        config_defaults=None,
        config_overrides=None,
    ):
        raise NotImplementedError

    @classmethod
    def verify_config(cls, config):
        salt.utils.verify.verify_env(
            cls._get_verify_config_entries(config),
            running_username(),
            pki_dir=config.get("pki_dir") or "",
            root_dir=config["root_dir"],
        )

    @classmethod
    def _get_verify_config_entries(cls, config):
        raise NotImplementedError

    @classmethod
    def write_config(cls, config):
        config_file = config.pop("conf_file")
        log.debug(
            "Writing to configuration file %s. Configuration:\n%s",
            config_file,
            pprint.pformat(config),
        )

        # Write down the computed configuration into the config file
        with salt.utils.files.fopen(config_file, "w") as wfh:
            salt.utils.yaml.safe_dump(config, wfh, default_flow_style=False)
        loaded_config = cls.load_config(config_file, config)
        cls.verify_config(loaded_config)
        return loaded_config

    @classmethod
    def load_config(cls, config_file, config):
        """
        Should return the configuration as the daemon would have loaded after
        parsing the CLI
        """
        raise NotImplementedError

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        raise NotImplementedError

    def run_start_checks(self, started_at, timeout_at):
        if not super().run_start_checks(started_at, timeout_at):
            return False
        if not self.event_listener:
            return True

        check_events = set(self.get_check_events())
        if not check_events:
            return True
        checks_start_time = time.time()
        while time.time() <= timeout_at:
            if not self.is_running():
                log.info("%s is no longer running", self)
                return False
            if not check_events:
                break
            check_events -= self.event_listener.get_events(check_events, after_time=started_at)
        else:
            log.error("Failed to check events after %1.2f seconds", time.time() - checks_start_time)
            return False
        return True

    def build_cmdline(self, *args):
        cmdline = super().build_cmdline(*args)
        if self.python_executable:
            if cmdline[0] != self.python_executable:
                cmdline.insert(0, self.python_executable)
        return cmdline
