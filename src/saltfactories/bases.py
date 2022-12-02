"""
Factories base classes.
"""
import atexit
import contextlib
import json
import logging
import os
import pprint
from typing import TYPE_CHECKING

import attr
import psutil
import pytest
from pytestshellutils.exceptions import FactoryNotStarted
from pytestshellutils.shell import Daemon
from pytestshellutils.shell import DaemonImpl
from pytestshellutils.shell import ScriptSubprocess
from pytestshellutils.shell import Subprocess
from pytestshellutils.shell import SubprocessImpl
from pytestshellutils.utils import time
from pytestshellutils.utils.processes import ProcessResult
from pytestshellutils.utils.processes import terminate_process

from saltfactories.utils import running_username

log = logging.getLogger(__name__)

# If any --timeout is passed on the CLI, we'll feed it to salt,
# and will increase it internally as a hard timeout by the following amount
SALT_TIMEOUT_FLAG_INCREASE = 20


@attr.s(kw_only=True)
class SaltMixin:
    """
    Base factory for salt cli's and daemon's.

    :param dict config:
        The Salt config dictionary
    :param str python_executable:
        The path to the python executable to use
    :param bool system_service:
        If true, the daemons and CLI's are run against a system installed salt setup, ie, the default
        salt system paths apply.
    """

    config = attr.ib(repr=False)
    id = attr.ib(init=False)  # pylint: disable=invalid-name
    config_file = attr.ib(init=False)
    config_dir = attr.ib()
    python_executable = attr.ib(default=None)
    system_service = attr.ib(repr=False, default=False)
    display_name = attr.ib(init=False, default=None)

    def __attrs_post_init__(self):
        """
        Post attrs initialization routines.
        """
        # We really do not want buffered output
        self.environ.setdefault("PYTHONUNBUFFERED", "1")
        # Don't write .pyc files or create them in __pycache__ directories
        self.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
        from salt.utils.immutabletypes import freeze

        self.config = freeze(self.config)

    @config_file.default
    def _default_config_file(self):
        return self.config["conf_file"]

    @config_dir.default
    def _default_config_dir(self):
        return os.path.dirname(self.config_file)

    @id.default
    def _default_id(self):
        return self.config["id"]

    def get_display_name(self):
        """
        Returns a human readable name for the factory.
        """
        if self.display_name is None:
            self.display_name = "{}(id={!r})".format(self.__class__.__name__, self.id)
        if self.display_name is not None:
            return self.display_name
        return super().get_display_name()


@attr.s(kw_only=True)
class SaltCliImpl(SubprocessImpl):
    """
    Salt CLI's subprocess interaction implementation.

    Please look at :py:class:`~pytestshellutils.shell.SubprocessImpl` for the additional
    supported keyword arguments documentation.
    """

    def cmdline(self, *args, minion_tgt=None, **kwargs):  # pylint: disable=arguments-differ
        """
        Construct a list of arguments to use when starting the subprocess.

        :param str args:
            Additional arguments to use when starting the subprocess
        :keyword str minion_tgt:
            The minion ID to target
        :keyword kwargs:
            Additional keyword arguments will be converted into ``key=value`` pairs to be consumed by the salt CLI's
        """
        return self.factory.cmdline(*args, minion_tgt=minion_tgt, **kwargs)


@attr.s(kw_only=True)
class SaltCli(SaltMixin, ScriptSubprocess):
    """
    Base factory for salt cli's.

    :param bool hard_crash:
        Pass ``--hard-crash`` to Salt's CLI's

    Please look at :py:class:`~saltfactories.bases.Salt` and
    :py:class:`~pytestshellutils.shell.ScriptSubprocess` for the additional supported keyword
    arguments documentation.
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
        return SaltCliImpl

    def __attrs_post_init__(self):
        """
        Post attrs initialization routines.
        """
        ScriptSubprocess.__attrs_post_init__(self)
        SaltMixin.__attrs_post_init__(self)

    def get_script_args(self):
        """
        Returns any additional arguments to pass to the CLI script.
        """
        if not self.hard_crash:
            return super().get_script_args()
        return ["--hard-crash"]

    def get_minion_tgt(self, minion_tgt=None):
        """
        Return the minion target ID.
        """
        return minion_tgt

    def cmdline(
        self, *args, minion_tgt=None, merge_json_output=None, **kwargs
    ):  # pylint: disable=arguments-differ
        """
        Construct a list of arguments to use when starting the subprocess.

        :param str args:
            Additional arguments to use when starting the subprocess
        :keyword str minion_tgt:
            The minion ID to target
        :keyword bool merge_json_output:
            The default behavior of salt outputters is to print one line per minion return, which makes
            parsing the whole output as JSON impossible when targeting multiple minions. If this value
            is ``True``, an attempt is made to merge each JSON line into a single dictionary.
        :keyword kwargs:
            Additional keyword arguments will be converted into ``key=value`` pairs to be consumed by the salt CLI's
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
                    if self.impl._terminal_timeout is None:
                        self.impl._terminal_timeout = (
                            int(salt_cli_timeout) + SALT_TIMEOUT_FLAG_INCREASE
                        )
                    elif salt_cli_timeout >= self.impl._terminal_timeout:
                        self.impl._terminal_timeout = (
                            int(salt_cli_timeout) + SALT_TIMEOUT_FLAG_INCREASE
                        )
                    break
                if salt_cli_timeout_next:
                    try:
                        salt_cli_timeout = int(arg)
                    except ValueError:
                        # Not a number? Let salt do it's error handling
                        break
                    if self.impl._terminal_timeout is None:
                        self.impl._terminal_timeout = (
                            int(salt_cli_timeout) + SALT_TIMEOUT_FLAG_INCREASE
                        )
                    if salt_cli_timeout >= self.impl._terminal_timeout:
                        self.impl._terminal_timeout = (
                            int(salt_cli_timeout) + SALT_TIMEOUT_FLAG_INCREASE
                        )
                    break
                if arg == "-t" or arg.startswith("--timeout"):
                    salt_cli_timeout_next = True
                    continue
            else:
                salt_cli_timeout = self.timeout
                if salt_cli_timeout and self.impl._terminal_timeout:
                    if self.impl._terminal_timeout > salt_cli_timeout:
                        salt_cli_timeout = self.impl._terminal_timeout
                if not salt_cli_timeout and self.impl._terminal_timeout:
                    salt_cli_timeout = self.impl._terminal_timeout
                if salt_cli_timeout:
                    self.impl._terminal_timeout = salt_cli_timeout + SALT_TIMEOUT_FLAG_INCREASE
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
        for key, value in kwargs.items():
            if not isinstance(value, str):
                value = json.dumps(value)
            cmdline.append("{}={}".format(key, value))
        cmdline = super().cmdline(*cmdline)
        if self.python_executable:
            if cmdline[0] != self.python_executable:
                cmdline.insert(0, self.python_executable)
        log.debug("Built cmdline: %s", cmdline)
        return cmdline

    def process_output(self, stdout, stderr, cmdline=None):
        """
        Process the output. When possible JSON is loaded from the output.

        :return:
            Returns a tuple in the form of ``(stdout, stderr, loaded_json)``
        :rtype: tuple
        """
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
            except KeyError:  # pragma: no cover
                pass
        return stdout, stderr, json_out


@attr.s(kw_only=True)
class SystemdSaltDaemonImpl(DaemonImpl):
    """
    Daemon systemd interaction implementation.

    Please look at :py:class:`~pytestshellutils.shell.DaemonImpl` for the additional supported keyword
    arguments documentation.
    """

    _process = attr.ib(init=False, repr=False, default=None)
    _service_name = attr.ib(init=False, repr=False, default=None)

    def cmdline(self, *args):  # pylint: disable=arguments-differ
        """
        Construct a list of arguments to use when starting the subprocess.

        :param str args:
            Additional arguments to use when starting the subprocess

        """
        if args:  # pragma: no cover
            log.debug(
                "%s.run() is ignoring the passed in arguments: %r", self.__class__.__name__, args
            )
        return ("systemctl", "start", self.get_service_name())

    def get_service_name(self):
        """
        Return the systemd service name.
        """
        if self._service_name is None:
            script_path = self.factory.get_script_path()
            if os.path.isabs(script_path):
                script_path = os.path.basename(script_path)
            self._service_name = script_path
        return self._service_name

    def _internal_run(self, *cmdline):
        """
        Run the given command synchronously.
        """
        result = Subprocess(
            cwd=self.factory.cwd,
            environ=self.factory.environ.copy(),
            system_encoding=self.factory.system_encoding,
        ).run(*cmdline)
        log.info("%s %s", self.factory.__class__.__name__, result)
        return result

    def is_running(self):
        """
        Returns true if the sub-process is alive.
        """
        if self._process is None:
            ret = self._internal_run("systemctl", "show", "-p", "MainPID", self.get_service_name())
            mainpid = ret.stdout.split("=")[-1].strip()
            if mainpid == "0":
                return False
            self._process = psutil.Process(int(mainpid))
        return self._process.is_running()

    @property
    def pid(self):
        """
        Return the ``pid`` of the running process.
        """
        if self.is_running():
            return self._process.pid

    def start(self, *extra_cli_arguments, max_start_attempts=None, start_timeout=None):
        """
        Start the daemon.
        """
        started = super().start(
            *extra_cli_arguments, max_start_attempts=max_start_attempts, start_timeout=start_timeout
        )
        atexit.register(self.terminate)
        return started

    def _terminate(self):
        """
        This method actually terminates the started daemon.
        """
        # We completely override the parent class method because we're not using the
        # self._terminal property, it's a systemd service
        if self._process is None:  # pragma: no cover
            if TYPE_CHECKING:
                # Make mypy happy
                assert self._terminal_result
            return self._terminal_result  # pylint: disable=access-member-before-definition

        atexit.unregister(self.terminate)
        log.info("Stopping %s", self.factory)
        pid = self.pid
        # Collect any child processes information before terminating the process
        with contextlib.suppress(psutil.NoSuchProcess):
            for child in psutil.Process(pid).children(recursive=True):
                if child not in self._children:  # pylint: disable=access-member-before-definition
                    self._children.append(child)  # pylint: disable=access-member-before-definition

        if self._process.is_running():  # pragma: no cover
            cmdline = self._process.cmdline()
        else:
            # The main pid is not longer alive, try to get the cmdline from systemd
            ret = self._internal_run(
                "systemctl", "show", "-p", "ExecStart", self.get_service_name()
            )
            cmdline = ret.stdout.split("argv[]=")[-1].split(";")[0].strip().split()

        # Tell systemd to stop the service
        self._internal_run("systemctl", "stop", self.get_service_name())

        if self._process.is_running():  # pragma: no cover
            cmdline = self._process.cmdline()
            try:
                self._process.wait()
            except psutil.TimeoutExpired:
                self._process.terminate()
                try:
                    self._process.wait()
                except psutil.TimeoutExpired:
                    pass

        exitcode = self._process.wait() or 0

        # Dereference the internal _process attribute
        self._process = None
        # Lets log and kill any child processes left behind, including the main subprocess
        # if it failed to properly stop
        terminate_process(
            pid=pid,
            kill_children=True,
            children=self._children,  # pylint: disable=access-member-before-definition
            slow_stop=self.factory.slow_stop,
        )

        if self._terminal_stdout is not None:
            self._terminal_stdout.close()  # pylint: disable=access-member-before-definition
        if self._terminal_stderr is not None:
            self._terminal_stderr.close()  # pylint: disable=access-member-before-definition
        stdout = ""
        ret = self._internal_run("journalctl", "--no-pager", "-u", self.get_service_name())
        stderr = ret.stdout
        try:
            self._terminal_result = ProcessResult(
                returncode=exitcode, stdout=stdout, stderr=stderr, cmdline=cmdline
            )
            log.info("%s %s", self.factory.__class__.__name__, self._terminal_result)
            return self._terminal_result
        finally:
            self._terminal = None
            self._terminal_stdout = None
            self._terminal_stderr = None
            self._terminal_timeout = None
            self._children = []


@attr.s(kw_only=True)
class SaltDaemon(SaltMixin, Daemon):
    """
    Base factory for salt daemon's.

    Please look at :py:class:`~saltfactories.bases.SaltMixin` and
    :py:class:`~pytestshellutils.shell.Daemon` for the additional supported keyword
    arguments documentation.
    """

    display_name = attr.ib(init=False, default=None)
    event_listener = attr.ib(repr=False, default=None)
    factories_manager = attr.ib(repr=False, hash=False, default=None)
    _started_at = attr.ib(repr=False, default=None)

    def __attrs_post_init__(self):
        """
        Post attrs initialization routines.
        """
        Daemon.__attrs_post_init__(self)
        SaltMixin.__attrs_post_init__(self)

        if self.system_service is True and self.extra_cli_arguments_after_first_start_failure:
            raise pytest.UsageError(
                "You cannot pass `extra_cli_arguments_after_first_start_failure` to a salt "
                "system installation setup."
            )
        elif self.system_service is False:
            for arg in self.extra_cli_arguments_after_first_start_failure:
                if arg in ("-l", "--log-level"):
                    break
                if arg.startswith("--log-level="):
                    break
            else:
                self.extra_cli_arguments_after_first_start_failure.append("--log-level=debug")

        # Register before start function
        self.before_start(self._set_started_at)
        # Register start check function
        self.start_check(self._check_start_events)

    def _get_impl_class(self):
        if self.system_service:
            return SystemdSaltDaemonImpl
        return super()._get_impl_class()

    @classmethod
    def configure(
        cls,
        factories_manager,
        daemon_id,
        root_dir=None,
        defaults=None,
        overrides=None,
        **configure_kwargs
    ):
        """
        Configure the salt daemon.
        """
        return cls._configure(
            factories_manager,
            daemon_id,
            root_dir=root_dir,
            defaults=defaults,
            overrides=overrides,
            **configure_kwargs
        )

    @classmethod
    def _configure(
        cls,
        factories_manager,
        daemon_id,
        root_dir=None,
        defaults=None,
        overrides=None,
    ):
        raise NotImplementedError

    @classmethod
    def verify_config(cls, config):
        """
        Verify the configuration dictionary.
        """
        import salt.utils.verify

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
        """
        Write the configuration to file.
        """
        config_file = config.pop("conf_file")
        log.debug(
            "Writing to configuration file %s. Configuration:\n%s",
            config_file,
            pprint.pformat(config),
        )

        # Write down the computed configuration into the config file
        import salt.utils.files
        import salt.utils.yaml

        with salt.utils.files.fopen(config_file, "w") as wfh:
            salt.utils.yaml.safe_dump(config, wfh, default_flow_style=False)
        loaded_config = cls.load_config(config_file, config)
        cls.verify_config(loaded_config)
        return loaded_config

    @classmethod
    def load_config(cls, config_file, config):
        """
        Return the loaded configuration.

        Should return the configuration as the daemon would have loaded after
        parsing the CLI
        """
        raise NotImplementedError

    def get_check_events(self):
        """
        Return salt events to check.

        Returns list of tuples in the form of `(master_id, event_tag)` check against to
        ensure the daemon is running.
        """
        raise NotImplementedError

    def cmdline(self, *args):
        """
        Construct a list of arguments to use when starting the subprocess.

        :param str args:
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
        cmdline = super().cmdline(*(_args + list(args)))
        if self.python_executable:
            if cmdline[0] != self.python_executable:
                cmdline.insert(0, self.python_executable)
        return cmdline

    def _set_started_at(self):
        """
        Set the ``_started_at`` attribute on the daemon instance.
        """
        self._started_at = time.time()

    def _check_start_events(self, timeout_at):
        """
        Check for start events in the Salt event bus to confirm that the daemon is running.
        """
        if not self.event_listener:  # pragma: no cover
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
                for event in self.event_listener.get_events(
                    check_events, after_time=self._started_at
                )
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
