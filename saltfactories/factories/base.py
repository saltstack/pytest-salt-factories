"""
..
    PYTEST_DONT_REWRITE


saltfactories.factories.base
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Factories base classes
"""
import atexit
import contextlib
import json
import logging
import os
import pprint
import subprocess
import sys
import tempfile

import attr
import psutil
import pytest
import salt.utils.files
import salt.utils.path
import salt.utils.verify
import salt.utils.yaml
from salt.utils.immutabletypes import freeze

from saltfactories.exceptions import FactoryNotRunning
from saltfactories.exceptions import FactoryNotStarted
from saltfactories.exceptions import FactoryTimeout
from saltfactories.utils import platform
from saltfactories.utils import ports
from saltfactories.utils import running_username
from saltfactories.utils import time
from saltfactories.utils.processes import ProcessResult
from saltfactories.utils.processes import ShellResult
from saltfactories.utils.processes import terminate_process
from saltfactories.utils.processes import terminate_process_list

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
class SubprocessFactoryImpl:
    """
    Subprocess interaction implementation
    """

    factory = attr.ib()

    _terminal = attr.ib(repr=False, init=False, default=None)
    _terminal_stdout = attr.ib(repr=False, init=False, default=None)
    _terminal_stderr = attr.ib(repr=False, init=False, default=None)
    _terminal_result = attr.ib(repr=False, init=False, default=None)
    _terminal_timeout = attr.ib(repr=False, init=False, default=None)
    _children = attr.ib(repr=False, init=False, default=attr.Factory(list))

    def build_cmdline(self, *args):
        """
        Construct a list of arguments to use when starting the subprocess

        Args:
            args:
                Additional arguments to use when starting the subprocess
        """
        return self.factory.build_cmdline(*args)

    def init_terminal(self, cmdline, env=None, **kwargs):
        """
        Instantiate a terminal with the passed cmdline and kwargs and return it.

        Additionally, it sets a reference to it in self._terminal and also collects
        an initial listing of child processes which will be used when terminating the
        terminal
        """
        for key in ("stdin", "stdout", "stderr", "close_fds", "shell", "cwd"):
            if key in kwargs:
                raise RuntimeError(
                    "{}.{}.init_terminal() does not accept {} as a valid keyword argument".format(
                        __name__, self.__class__.__name__, key
                    )
                )
        environ = self.factory.environ.copy()
        if env is not None:
            environ.update(env)
        self._terminal_stdout = tempfile.SpooledTemporaryFile(512000, buffering=0)
        self._terminal_stderr = tempfile.SpooledTemporaryFile(512000, buffering=0)
        if platform.is_windows():
            # Windows does not support closing FDs
            close_fds = False
        elif platform.is_freebsd() and sys.version_info < (3, 9):
            # Closing FDs in FreeBSD before Py3.9 can be slow
            #   https://bugs.python.org/issue38061
            close_fds = False
        else:
            close_fds = True
        self._terminal = subprocess.Popen(
            cmdline,
            stdout=self._terminal_stdout,
            stderr=self._terminal_stderr,
            shell=False,
            cwd=self.factory.cwd,
            universal_newlines=True,
            close_fds=close_fds,
            env=environ,
        )
        # Reset the previous _terminal_result if set
        self._terminal_result = None
        try:
            # Check if the process starts properly
            self._terminal.wait(timeout=0.05)
            # If TimeoutExpired is not raised, it means the process failed to start
        except subprocess.TimeoutExpired:
            # We're good
            with contextlib.suppress(psutil.NoSuchProcess):
                for child in psutil.Process(self._terminal.pid).children(recursive=True):
                    if child not in self._children:
                        self._children.append(child)
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
        return self._terminate()

    def _terminate(self):
        """
        This method actually terminates the started daemon
        """
        if self._terminal is None:
            return self._terminal_result
        atexit.unregister(self.terminate)
        log.info("Stopping %s", self.factory)
        # Collect any child processes information before terminating the process
        with contextlib.suppress(psutil.NoSuchProcess):
            for child in psutil.Process(self._terminal.pid).children(recursive=True):
                if child not in self._children:
                    self._children.append(child)

        with self._terminal:
            if self.factory.slow_stop:
                self._terminal.terminate()
            else:
                self._terminal.kill()
            try:
                # Allow the process to exit by itself in case slow_stop is True
                self._terminal.wait(10)
            except subprocess.TimeoutExpired:
                # The process failed to stop, no worries, we'll make sure it exit along with it's
                # child processes bellow
                pass
            # Lets log and kill any child processes left behind, including the main subprocess
            # if it failed to properly stop
            terminate_process(
                pid=self._terminal.pid,
                kill_children=True,
                children=self._children,
                slow_stop=self.factory.slow_stop,
            )
            # Wait for the process to terminate, to avoid zombies.
            self._terminal.wait()
            # poll the terminal so the right returncode is set on the popen object
            self._terminal.poll()
            # This call shouldn't really be necessary
            self._terminal.communicate()

            self._terminal_stdout.flush()
            self._terminal_stdout.seek(0)
            if sys.version_info < (3, 6):
                stdout = self._terminal._translate_newlines(
                    self._terminal_stdout.read(), __salt_system_encoding__
                )
            else:
                stdout = self._terminal._translate_newlines(
                    self._terminal_stdout.read(), __salt_system_encoding__, sys.stdout.errors
                )
            self._terminal_stdout.close()

            self._terminal_stderr.flush()
            self._terminal_stderr.seek(0)
            if sys.version_info < (3, 6):
                stderr = self._terminal._translate_newlines(
                    self._terminal_stderr.read(), __salt_system_encoding__
                )
            else:
                stderr = self._terminal._translate_newlines(
                    self._terminal_stderr.read(), __salt_system_encoding__, sys.stderr.errors
                )
            self._terminal_stderr.close()
        try:
            self._terminal_result = ProcessResult(
                self._terminal.returncode, stdout, stderr, cmdline=self._terminal.args
            )
            log.info("%s %s", self.factory.__class__.__name__, self._terminal_result)
            return self._terminal_result
        finally:
            self._terminal = None
            self._terminal_stdout = None
            self._terminal_stderr = None
            self._terminal_timeout = None
            self._children = []

    @property
    def pid(self):
        if not self._terminal:
            return
        return self._terminal.pid

    def run(self, *args, **kwargs):
        """
        Run the given command synchronously
        """
        cmdline = self.build_cmdline(*args, **kwargs)
        log.info("%s is running %r in CWD: %s ...", self.factory, cmdline, self.factory.cwd)
        return self.init_terminal(cmdline)


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

    impl = attr.ib(repr=False, init=False)

    @impl.default
    def _set_impl_default(self):
        impl_class = self._get_impl_class()
        return impl_class(factory=self)

    def _get_impl_class(self):
        return SubprocessFactoryImpl

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

    def is_running(self):
        """
        Returns true if the sub-process is alive
        """
        return self.impl.is_running()

    def terminate(self):
        """
        Terminate the started daemon
        """
        return self.impl.terminate()

    @property
    def pid(self):
        return self.impl.pid


@attr.s(kw_only=True)
class ProcessFactory(SubprocessFactoryBase):
    """
    Base process factory

    Args:
        default_timeout(int):
            The maximum amount of seconds that a script should run
    """

    default_timeout = attr.ib()

    @default_timeout.default
    def _set_default_timeout(self):
        if not sys.platform.startswith(("win", "darwin")):
            return 60
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
        self.impl._terminal_timeout = _timeout or self.default_timeout
        timmed_out = False
        try:
            self.impl.run(*args, **kwargs)
            self.impl._terminal.communicate(timeout=self.impl._terminal_timeout)
        except subprocess.TimeoutExpired:
            timmed_out = True

        result = self.terminate()
        cmdline = result.cmdline
        exitcode = result.exitcode
        if timmed_out:
            raise FactoryTimeout(
                "{} Failed to run: {}; Error: Timed out after {:.2f} seconds!".format(
                    self, cmdline, time.time() - start_time
                ),
                stdout=result.stdout,
                stderr=result.stderr,
                cmdline=cmdline,
                exitcode=exitcode,
            )
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
                log.debug("%s failed to load JSON from the following output:\n%r", self, stdout)
                json_out = None
        else:
            json_out = None
        return stdout, stderr, json_out


@attr.s(kw_only=True)
class StartDaemonCallArguments:

    args = attr.ib()
    kwargs = attr.ib()


@attr.s(kw_only=True)
class DaemonFactoryImpl(SubprocessFactoryImpl):
    """
    Daemon subprocess interaction implementation
    """

    before_start_callbacks = attr.ib(repr=False, hash=False, default=attr.Factory(list))
    before_terminate_callbacks = attr.ib(repr=False, hash=False, default=attr.Factory(list))
    after_start_callbacks = attr.ib(repr=False, hash=False, default=attr.Factory(list))
    after_terminate_callbacks = attr.ib(repr=False, hash=False, default=attr.Factory(list))
    _start_args_and_kwargs = attr.ib(init=False, repr=False, hash=False)

    def register_before_start_callback(self, callback, *args, **kwargs):
        self.before_start_callbacks.append((callback, args, kwargs))

    def register_before_terminate_callback(self, callback, *args, **kwargs):
        self.before_terminate_callbacks.append((callback, args, kwargs))

    def register_after_start_callback(self, callback, *args, **kwargs):
        self.after_start_callbacks.append((callback, args, kwargs))

    def register_after_terminate_callback(self, callback, *args, **kwargs):
        self.after_terminate_callbacks.append((callback, args, kwargs))

    def _format_callback(self, callback, args, kwargs):
        callback_str = "{}(".format(callback.__name__)
        if args:
            callback_str += ", ".join([repr(arg) for arg in args])
        if kwargs:
            callback_str += ", ".join(["{}={!r}".format(k, v) for (k, v) in kwargs.items()])
        callback_str += ")"
        return callback_str

    def start(self, *extra_cli_arguments, max_start_attempts=None, start_timeout=None):
        """
        Start the daemon
        """
        if self.is_running():
            log.warning("%s is already running.", self)
            return True
        self._start_args_and_kwargs = StartDaemonCallArguments(
            args=extra_cli_arguments,
            kwargs={"max_start_attempts": max_start_attempts, "start_timeout": start_timeout},
        )
        process_running = False
        start_time = time.time()
        start_attempts = max_start_attempts or self.factory.max_start_attempts
        current_attempt = 0
        run_arguments = list(extra_cli_arguments)
        while True:
            if process_running:
                break
            current_attempt += 1
            if current_attempt > start_attempts:
                break
            log.info(
                "Starting %s. Attempt: %d of %d", self.factory, current_attempt, start_attempts
            )
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
            current_start_time = time.time()
            start_running_timeout = current_start_time + (
                start_timeout or self.factory.start_timeout
            )
            if current_attempt > 1 and self.factory.extra_cli_arguments_after_first_start_failure:
                run_arguments = list(extra_cli_arguments) + list(
                    self.factory.extra_cli_arguments_after_first_start_failure
                )
            self.run(*run_arguments)
            if not self.is_running():
                # A little breathe time to allow the process to start if not started already
                time.sleep(0.5)
            while time.time() <= start_running_timeout:
                if not self.is_running():
                    log.warning("%s is no longer running", self.factory)
                    self.terminate()
                    break
                try:
                    if (
                        self.factory.run_start_checks(current_start_time, start_running_timeout)
                        is False
                    ):
                        time.sleep(1)
                        continue
                except FactoryNotStarted:
                    self.terminate()
                    break
                log.info(
                    "The %s factory is running after %d attempts. Took %1.2f seconds",
                    self.factory,
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
            return process_running
        result = self.terminate()
        raise FactoryNotStarted(
            "The {} factory has failed to confirm running status after {} attempts, which "
            "took {:.2f} seconds".format(
                self.factory,
                current_attempt - 1,
                time.time() - start_time,
            ),
            stdout=result.stdout,
            stderr=result.stderr,
            exitcode=result.exitcode,
            cmdline=result.cmdline,
        )

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

    def get_start_arguments(self):
        return self._start_args_and_kwargs


@attr.s(kw_only=True)
class DaemonFactory(SubprocessFactoryBase):
    """
    Base daemon factory
    """

    check_ports = attr.ib(default=None)
    factories_manager = attr.ib(repr=False, hash=False, default=None)
    start_timeout = attr.ib(repr=False)
    max_start_attempts = attr.ib(repr=False, default=3)
    extra_cli_arguments_after_first_start_failure = attr.ib(hash=False, default=attr.Factory(list))
    listen_ports = attr.ib(init=False, repr=False, hash=False, default=attr.Factory(list))

    def _get_impl_class(self):
        return DaemonFactoryImpl

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.check_ports and not isinstance(self.check_ports, (list, tuple)):
            self.check_ports = [self.check_ports]
        if self.check_ports:
            self.listen_ports.extend(self.check_ports)

        self.register_after_start_callback(self._add_factory_to_stats_processes)
        self.register_after_terminate_callback(self._terminate_processes_matching_listen_ports)
        self.register_after_terminate_callback(self._remove_factory_from_stats_processes)

    def register_before_start_callback(self, callback, *args, **kwargs):
        self.impl.before_start_callbacks.append((callback, args, kwargs))

    def register_before_terminate_callback(self, callback, *args, **kwargs):
        self.impl.before_terminate_callbacks.append((callback, args, kwargs))

    def register_after_start_callback(self, callback, *args, **kwargs):
        self.impl.after_start_callbacks.append((callback, args, kwargs))

    def register_after_terminate_callback(self, callback, *args, **kwargs):
        self.impl.after_terminate_callbacks.append((callback, args, kwargs))

    def get_check_ports(self):
        """
        Return a list of ports to check against to ensure the daemon is running
        """
        return self.check_ports or []

    def start(self, *extra_cli_arguments, max_start_attempts=None, start_timeout=None):
        """
        Start the daemon
        """
        return self.impl.start(
            *extra_cli_arguments, max_start_attempts=max_start_attempts, start_timeout=start_timeout
        )

    def started(self, *extra_cli_arguments, max_start_attempts=None, start_timeout=None):
        """
        Start the daemon and return it's instance so it can be used as a context manager
        """
        self.start(
            *extra_cli_arguments, max_start_attempts=max_start_attempts, start_timeout=start_timeout
        )
        return self

    @contextlib.contextmanager
    def stopped(self):
        """
        This context manager will stop the factory while the context is in place, it re-starts it once out of
        context.

        For example:

        .. code-block:: python

            assert factory.is_running() is True

            with factory.stopped():
                assert factory.is_running() is False

            assert factory.is_running() is True
        """
        if not self.is_running():
            raise FactoryNotRunning("{} is not running ".format(self))
        start_arguments = self.impl.get_start_arguments()
        try:
            self.terminate()
            yield
        except Exception:  # pylint: disable=broad-except,try-except-raise
            raise
        else:
            return self.started(*start_arguments.args, **start_arguments.kwargs)

    def run_start_checks(self, started_at, timeout_at):
        log.debug("%s is running start checks", self)
        check_ports = set(self.get_check_ports())
        if not check_ports:
            log.debug("No ports to check connection to for %s", self)
            return True
        log.debug("Listening ports to check for %s: %s", self, set(self.get_check_ports()))
        checks_start_time = time.time()
        while time.time() <= timeout_at:
            if not self.is_running():
                raise FactoryNotStarted("{} is no longer running".format(self))
            if not check_ports:
                break
            check_ports -= ports.get_connectable_ports(check_ports)
            if check_ports:
                time.sleep(1.5)
        else:
            log.error(
                "Failed to check ports after %1.2f seconds for %s. Remaining ports to check: %s",
                time.time() - checks_start_time,
                self,
                check_ports,
            )
            return False
        log.debug("All listening ports checked for %s: %s", self, set(self.get_check_ports()))
        return True

    def _add_factory_to_stats_processes(self):
        if self.factories_manager and self.factories_manager.stats_processes is not None:
            display_name = self.get_display_name()
            self.factories_manager.stats_processes.add(display_name, self.pid)

    def _remove_factory_from_stats_processes(self):
        if self.factories_manager and self.factories_manager.stats_processes is not None:
            display_name = self.get_display_name()
            self.factories_manager.stats_processes.remove(display_name)

    def _terminate_processes_matching_listen_ports(self):
        if not self.listen_ports:
            return
        # If any processes were not terminated and are listening on the ports
        # we have set on listen_ports, terminate those processes.
        found_processes = []
        for process in psutil.process_iter(["connections"]):
            try:
                for connection in process.connections():
                    if connection.status != psutil.CONN_LISTEN:
                        # We only care about listening services
                        continue
                    if connection.laddr.port in self.check_ports:
                        found_processes.append(process)
                        # We already found one connection, no need to check the others
                        break
            except psutil.AccessDenied:
                # We've been denied access to this process connections. Carry on.
                continue
        if found_processes:
            log.debug(
                "The following processes were found listening on ports %s: %s",
                ", ".join([str(port) for port in self.listen_ports]),
                found_processes,
            )
            terminate_process_list(found_processes, kill=True, slow_stop=False)
        else:
            log.debug(
                "No astray processes were found listening on ports: %s",
                ", ".join([str(port) for port in self.listen_ports]),
            )

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
        system_install(bool):
            If true, the daemons and CLI's are run against a system installed salt setup, ie, the default
            salt system paths apply.
    """

    id = attr.ib(default=None, init=False)
    config = attr.ib(repr=False)
    config_dir = attr.ib(init=False, default=None)
    config_file = attr.ib(init=False, default=None)
    python_executable = attr.ib(default=None)
    system_install = attr.ib(repr=False, default=False)
    display_name = attr.ib(init=False, default=None)

    def __attrs_post_init__(self):
        if self.python_executable is None and self.system_install is False:
            self.python_executable = sys.executable
        # We really do not want buffered output
        self.environ.setdefault("PYTHONUNBUFFERED", "1")
        # Don't write .pyc files or create them in __pycache__ directories
        self.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
        self.config_file = self.config["conf_file"]
        self.config_dir = os.path.dirname(self.config_file)
        self.id = self.config["id"]
        self.config = freeze(self.config)

    def get_display_name(self):
        """
        Returns a human readable name for the factory
        """
        if self.display_name is None:
            self.display_name = "{}(id={!r})".format(self.__class__.__name__, self.id)
        return super().get_display_name()


@attr.s(kw_only=True)
class SaltCliFactoryImpl(SubprocessFactoryImpl):
    """
    Subprocess interaction implementation
    """

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
        return self.factory.build_cmdline(*args, minion_tgt=minion_tgt, **kwargs)


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
    merge_json_output = attr.ib(repr=False, default=True)

    __cli_timeout_supported__ = attr.ib(repr=False, init=False, default=False)
    __cli_log_level_supported__ = attr.ib(repr=False, init=False, default=True)
    __cli_output_supported__ = attr.ib(repr=False, init=False, default=True)
    __json_output__ = attr.ib(repr=False, init=False, default=False)
    __merge_json_output__ = attr.ib(repr=False, init=False, default=True)

    def _get_impl_class(self):
        return SaltCliFactoryImpl

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

    def build_cmdline(
        self, *args, minion_tgt=None, merge_json_output=None, **kwargs
    ):  # pylint: disable=arguments-differ
        """
        Construct a list of arguments to use when starting the subprocess

        Args:
            args:
                Additional arguments to use when starting the subprocess
            kwargs:
                Keyword arguments will be converted into ``key=value`` pairs to be consumed by the salt CLI's
            minion_tgt(str):
                The minion ID to target
            merge_json_output(bool):
                The default behavior of salt outputters is to print one line per minion return, which makes
                parsing the whole output as JSON impossible when targeting multiple minions. If this value
                is ``True``, an attempt is made to merge each JSON line into a single dictionary.
        """
        log.debug(
            "Building cmdline. Minion target: %s; Input args: %s; Input kwargs: %s;",
            minion_tgt,
            args,
            kwargs,
        )
        minion_tgt = self._minion_tgt = self.get_minion_tgt(minion_tgt=minion_tgt)
        if merge_json_output is None:
            self.__merge_json_output__ = self.merge_json_output
        else:
            self.__merge_json_output__ = merge_json_output
        cmdline = []

        # Convert all passed in arguments to strings
        args = [str(arg) for arg in args]

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
                    try:
                        salt_cli_timeout = int(arg.split("--timeout=")[-1])
                    except ValueError:
                        # Not a number? Let salt do it's error handling
                        break
                    if salt_cli_timeout >= self.impl._terminal_timeout:
                        self.impl._terminal_timeout = int(salt_cli_timeout) + 10
                    break
                if salt_cli_timeout_next:
                    try:
                        salt_cli_timeout = int(arg)
                    except ValueError:
                        # Not a number? Let salt do it's error handling
                        break
                    if salt_cli_timeout >= self.impl._terminal_timeout:
                        self.impl._terminal_timeout = int(salt_cli_timeout) + 10
                    break
                if arg == "-t" or arg.startswith("--timeout"):
                    salt_cli_timeout_next = True
                    continue
            else:
                # Pass the default timeout to salt and increase the internal timeout by 10 seconds to
                # allow salt to exit cleanly.
                salt_cli_timeout = self.impl._terminal_timeout
                if salt_cli_timeout:
                    self.impl._terminal_timeout = salt_cli_timeout + 10
                    # Add it to the salt command CLI flags
                    cmdline.append("--timeout={}".format(salt_cli_timeout))

        # Handle the output flag
        if self.__cli_output_supported__:
            for idx, arg in enumerate(args):
                if arg in ("--out", "--output"):
                    self.__json_output__ = args[idx + 1] == "json"
                    break
                if arg.startswith(("--out=", "--output=")):
                    self.__json_output__ = arg.split("=")[-1].strip() == "json"
                    break
            else:
                # No output was passed, the default output is JSON
                cmdline.append("--out=json")
                self.__json_output__ = True
            if self.__json_output__:
                for arg in args:
                    if arg in ("--out-indent", "--output-indent"):
                        break
                    if arg.startswith(("--out-indent=", "--output-indent=")):
                        break
                else:
                    # Default to one line per output
                    cmdline.append("--out-indent=0")

        if self.__cli_log_level_supported__:
            # Handle the logging flag
            for arg in args:
                if arg in ("-l", "--log-level"):
                    break
                if arg.startswith("--log-level="):
                    break
            else:
                # Default to being almost quiet on console output
                cmdline.append("--log-level=critical")

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
        json_out = None
        if stdout and self.__json_output__:
            try:
                json_out = json.loads(stdout)
            except ValueError:
                if self.__merge_json_output__:
                    try:
                        json_out = json.loads(stdout.replace("}\n{", ", "))
                    except ValueError:
                        pass
            if json_out is None:
                log.debug("%s failed to load JSON from the following output:\n%r", self, stdout)
        if (
            self.__cli_output_supported__
            and json_out
            and isinstance(json_out, str)
            and self.__json_output__
        ):
            # Sometimes the parsed JSON is just a string, for example:
            #  OUTPUT: '"The salt master could not be contacted. Is master running?"\n'
            #  LOADED JSON: 'The salt master could not be contacted. Is master running?'
            #
            # In this case, we assign the loaded JSON to stdout and reset json_out
            stdout = json_out
            json_out = None
        if (
            self.__cli_output_supported__
            and json_out
            and self._minion_tgt
            and self._minion_tgt != "*"
        ):
            try:
                json_out = json_out[self._minion_tgt]
            except KeyError:
                pass
        return stdout, stderr, json_out


@attr.s(kw_only=True)
class SystemdSaltDaemonFactoryImpl(DaemonFactoryImpl):
    """
    Daemon systemd interaction implementation
    """

    _process = attr.ib(init=False, repr=False, default=None)
    _service_name = attr.ib(init=False, repr=False, default=None)

    def build_cmdline(self, *args):
        """
        Construct a list of arguments to use when starting the subprocess

        Args:
            args:
                Additional arguments to use when starting the subprocess
        """
        if args:
            log.debug(
                "%s.run() is ignoring the passed in arguments: %r", self.__class__.__name__, args
            )
        return ("systemctl", "start", self.get_service_name())

    def get_service_name(self):
        if self._service_name is None:
            script_path = self.factory.get_script_path()
            if os.path.isabs(script_path):
                script_path = os.path.basename(script_path)
            self._service_name = script_path
        return self._service_name

    def is_running(self):
        """
        Returns true if the sub-process is alive
        """
        if self._process is None:
            ret = self.internal_run("systemctl", "show", "-p", "MainPID", self.get_service_name())
            _, mainpid = ret.stdout.split("=")
            if mainpid == "0":
                return False
            self._process = psutil.Process(int(mainpid))
        return self._process.is_running()

    def internal_run(self, *args, **kwargs):
        """
        Run the given command synchronously
        """
        result = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
            **kwargs
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        process_result = ProcessResult(result.returncode, stdout, stderr, cmdline=result.args)
        log.info("%s %s", self.factory.__class__.__name__, process_result)
        return process_result

    def start(self, *extra_cli_arguments, max_start_attempts=None, start_timeout=None):
        started = super().start(
            *extra_cli_arguments, max_start_attempts=max_start_attempts, start_timeout=start_timeout
        )
        atexit.register(self.terminate)
        return started

    def _terminate(self):
        """
        This method actually terminates the started daemon
        """
        if self._process is None:
            return self._terminal_result
        atexit.unregister(self.terminate)
        log.info("Stopping %s", self.factory)
        # Collect any child processes information before terminating the process
        with contextlib.suppress(psutil.NoSuchProcess):
            for child in psutil.Process(self.pid).children(recursive=True):
                if child not in self._children:
                    self._children.append(child)

        pid = self.pid
        cmdline = self._process.cmdline()
        self.internal_run("systemctl", "stop", self.get_service_name())
        if self._process.is_running():
            try:
                self._process.wait()
            except psutil.TimeoutExpired:
                self._process.terminate()
                try:
                    self._process.wait()
                except psutil.TimeoutExpired:
                    pass
        exitcode = self._process.wait() or 0

        self._process = None
        # Lets log and kill any child processes left behind, including the main subprocess
        # if it failed to properly stop
        terminate_process(
            pid=pid,
            kill_children=True,
            children=self._children,
            slow_stop=self.factory.slow_stop,
        )

        self._terminal_stdout.close()
        self._terminal_stderr.close()
        stdout = ""
        ret = self.internal_run("journalctl", "--no-pager", "-u", self.get_service_name())
        stderr = ret.stdout
        try:
            self._terminal_result = ProcessResult(exitcode, stdout, stderr, cmdline=cmdline)
            log.info("%s %s", self.factory.__class__.__name__, self._terminal_result)
            return self._terminal_result
        finally:
            self._terminal = None
            self._terminal_stdout = None
            self._terminal_stderr = None
            self._terminal_timeout = None
            self._children = []

    @property
    def pid(self):
        if self.is_running():
            return self._process.pid


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

        if self.system_install is True and self.extra_cli_arguments_after_first_start_failure:
            raise RuntimeError(
                "You cannot pass `extra_cli_arguments_after_first_start_failure` to a salt "
                "system installation setup."
            )
        elif self.system_install is False:
            for arg in self.extra_cli_arguments_after_first_start_failure:
                if arg in ("-l", "--log-level"):
                    break
                if arg.startswith("--log-level="):
                    break
            else:
                self.extra_cli_arguments_after_first_start_failure.append("--log-level=debug")

    def _get_impl_class(self):
        if self.system_install:
            return SystemdSaltDaemonFactoryImpl
        return super()._get_impl_class()

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

    def build_cmdline(self, *args):
        """
        Construct a list of arguments to use when starting the subprocess

        Args:
            args:
                Additional arguments to use when starting the subprocess
        """
        _args = []
        # Handle the config directory flag
        for arg in args:
            if not isinstance(arg, str):
                continue
            if arg.startswith("--config-dir="):
                break
            if arg in ("-c", "--config-dir"):
                break
        else:
            _args.append("--config-dir={}".format(self.config_dir))
        # Handle the logging flag
        for arg in args:
            if not isinstance(arg, str):
                continue
            if arg in ("-l", "--log-level"):
                break
            if arg.startswith("--log-level="):
                break
        else:
            # Default to being almost quiet on console output
            _args.append("--log-level=critical")
        cmdline = super().build_cmdline(*(_args + list(args)))
        if self.python_executable:
            if cmdline[0] != self.python_executable:
                cmdline.insert(0, self.python_executable)
        return cmdline

    def run_start_checks(self, started_at, timeout_at):
        if not super().run_start_checks(started_at, timeout_at):
            return False
        if not self.event_listener:
            log.debug("The 'event_listener' attribute is not set. Not checking events...")
            return True

        check_events = set(self.get_check_events())
        if not check_events:
            log.debug("No events to listen to for %s", self)
            return True
        log.debug("Events to check for %s: %s", self, set(self.get_check_events()))
        checks_start_time = time.time()
        while time.time() <= timeout_at:
            if not self.is_running():
                raise FactoryNotStarted("{} is no longer running".format(self))
            if not check_events:
                break
            check_events -= {
                (event.daemon_id, event.tag)
                for event in self.event_listener.get_events(check_events, after_time=started_at)
            }
            if check_events:
                time.sleep(1.5)
        else:
            log.error(
                "Failed to check events after %1.2f seconds for %s. Remaining events to check: %s",
                time.time() - checks_start_time,
                self,
                check_events,
            )
            return False
        log.debug("All events checked for %s: %s", self, set(self.get_check_events()))
        return True
