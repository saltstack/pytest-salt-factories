"""
    saltfactories.factories.daemons.container
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Container based factories
"""
import atexit
import logging
import os

import attr

from saltfactories import CODE_ROOT_DIR
from saltfactories.exceptions import FactoryNotStarted
from saltfactories.factories.base import Factory
from saltfactories.factories.base import SaltDaemonFactory
from saltfactories.factories.daemons.minion import SaltMinionFactory
from saltfactories.utils import ports
from saltfactories.utils import random_string
from saltfactories.utils import time
from saltfactories.utils.processes import ProcessResult

try:
    import docker
    from docker.errors import APIError

    HAS_DOCKER = True
except ImportError:  # pragma: no cover
    HAS_DOCKER = False

    class APIError(Exception):
        pass


try:
    from requests.exceptions import ConnectionError as RequestsConnectionError

    HAS_REQUESTS = True
except ImportError:  # pragma: no cover
    HAS_REQUESTS = False

    class RequestsConnectionError(ConnectionError):
        pass


try:
    import pywintypes

    PyWinTypesError = pywintypes.error
except ImportError:

    class PyWinTypesError(Exception):
        pass


log = logging.getLogger(__name__)


@attr.s(kw_only=True)
class ContainerFactory(Factory):
    image = attr.ib()
    name = attr.ib(default=None)
    check_ports = attr.ib(default=None)
    docker_client = attr.ib(repr=False, default=None)
    container_run_kwargs = attr.ib(repr=False, default=attr.Factory(dict))
    container = attr.ib(init=False, default=None, repr=False)
    start_timeout = attr.ib(repr=False, default=30)
    max_start_attempts = attr.ib(repr=False, default=3)
    before_start_callbacks = attr.ib(repr=False, hash=False, default=attr.Factory(list))
    before_terminate_callbacks = attr.ib(repr=False, hash=False, default=attr.Factory(list))
    after_start_callbacks = attr.ib(repr=False, hash=False, default=attr.Factory(list))
    after_terminate_callbacks = attr.ib(repr=False, hash=False, default=attr.Factory(list))
    _terminate_result = attr.ib(repr=False, hash=False, init=False, default=None)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.name is None:
            self.name = random_string("factories-")
        if self.docker_client is None:
            if not HAS_DOCKER:
                raise RuntimeError("The docker python library was not found installed")
            if not HAS_REQUESTS:
                raise RuntimeError("The requests python library was not found installed")
            self.docker_client = docker.from_env()

    def _format_callback(self, callback, args, kwargs):
        callback_str = "{}(".format(callback.__name__)
        if args:
            callback_str += ", ".join([repr(arg) for arg in args])
        if kwargs:
            callback_str += ", ".join(["{}={!r}".format(k, v) for (k, v) in kwargs.items()])
        callback_str += ")"
        return callback_str

    def register_before_start_callback(self, callback, *args, **kwargs):
        self.before_start_callbacks.append((callback, args, kwargs))

    def register_before_terminate_callback(self, callback, *args, **kwargs):
        self.before_terminate_callbacks.append((callback, args, kwargs))

    def register_after_start_callback(self, callback, *args, **kwargs):
        self.after_start_callbacks.append((callback, args, kwargs))

    def register_after_terminate_callback(self, callback, *args, **kwargs):
        self.after_terminate_callbacks.append((callback, args, kwargs))

    def start(self, *command, max_start_attempts=None, start_timeout=None):
        if self.is_running():
            log.warning("%s is already running.", self)
            return True
        connectable = ContainerFactory.client_connectable(self.docker_client)
        if connectable is not True:
            self.terminate()
            raise RuntimeError(connectable)
        self._terminate_result = None
        atexit.register(self.terminate)
        factory_started = False
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
            if factory_started:
                break
            log.info("Starting %s. Attempt: %d of %d", self, current_attempt, start_attempts)
            current_start_time = time.time()
            start_running_timeout = current_start_time + (start_timeout or self.start_timeout)

            # Start the container
            self.container = self.docker_client.containers.run(
                self.image,
                name=self.name,
                detach=True,
                stdin_open=True,
                command=list(command) or None,
                **self.container_run_kwargs
            )
            while time.time() <= start_running_timeout:
                # Don't know why, but if self.container wasn't previously in a running
                # state, and now it is, we have to re-set the self.container attribute
                # so that it gives valid status information
                self.container = self.docker_client.containers.get(self.name)
                if self.container.status != "running":
                    time.sleep(0.25)
                    continue

                self.container = self.docker_client.containers.get(self.name)
                logs = self.container.logs(stdout=True, stderr=True, stream=False)
                if isinstance(logs, bytes):
                    stdout = logs.decode()
                    stderr = None
                else:
                    stdout = logs[0].decode()
                    stderr = logs[1].decode()
                if stdout and stderr:
                    log.info("Running Container Logs:\n%s\n%s", stdout, stderr)
                elif stdout:
                    log.info("Running Container Logs:\n%s", stdout)

                # If we reached this far it means that we got the running status above, and
                # now that the container has started, run start checks
                try:
                    if (
                        self.run_container_start_checks(current_start_time, start_running_timeout)
                        is False
                    ):
                        time.sleep(0.5)
                        continue
                except FactoryNotStarted:
                    self.terminate()
                    break
                log.info(
                    "The %s factory is running after %d attempts. Took %1.2f seconds",
                    self,
                    current_attempt,
                    time.time() - start_time,
                )
                factory_started = True
                break
            else:
                # We reached start_running_timeout, re-try
                try:
                    self.container.remove(force=True)
                    self.container.wait()
                except docker.errors.NotFound:
                    pass
                self.container = None
        else:
            # The factory failed to confirm it's running status
            self.terminate()
        if factory_started:
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
            # TODO: Add containers to the processes stats?!
            # if self.factories_manager and self.factories_manager.stats_processes is not None:
            #    self.factories_manager.stats_processes[self.get_display_name()] = psutil.Process(
            #        self.pid
            #    )
            return factory_started
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

    def started(self, *command, max_start_attempts=None, start_timeout=None):
        """
        Start the container and return it's instance so it can be used as a context manager
        """
        self.start(*command, max_start_attempts=max_start_attempts, start_timeout=start_timeout)
        return self

    def terminate(self):
        if self._terminate_result is not None:
            # The factory is already terminated
            return self._terminate_result
        atexit.unregister(self.terminate)
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
        stdout = stderr = None
        try:
            if self.container is not None:
                container = self.docker_client.containers.get(self.name)
                logs = container.logs(stdout=True, stderr=True, stream=False)
                if isinstance(logs, bytes):
                    stdout = logs.decode()
                else:
                    stdout = logs[0].decode()
                    stderr = logs[1].decode()
                if stdout and stderr:
                    log.info("Stopped Container Logs:\n%s\n%s", stdout, stderr)
                elif stdout:
                    log.info("Stopped Container Logs:\n%s", stdout)
                if container.status == "running":
                    container.remove(force=True)
                    container.wait()
                self.container = None
        except docker.errors.NotFound:
            pass
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
        self._terminate_result = ProcessResult(exitcode=0, stdout=stdout, stderr=stderr)
        return self._terminate_result

    def get_check_ports(self):
        """
        Return a list of ports to check against to ensure the daemon is running
        """
        return self.check_ports or []

    def is_running(self):
        if self.container is None:
            return False

        self.container = self.docker_client.containers.get(self.name)
        return self.container.status == "running"

    def run(self, *cmd, **kwargs):
        if len(cmd) == 1:
            cmd = cmd[0]
        log.info("%s is running %r ...", self, cmd)
        # We force dmux to True so that we always get back both stdout and stderr
        container = self.docker_client.containers.get(self.name)
        ret = container.exec_run(cmd, demux=True, **kwargs)
        exitcode = ret.exit_code
        stdout = stderr = None
        if ret.output:
            stdout, stderr = ret.output
        if stdout is not None:
            stdout = stdout.decode()
        if stderr is not None:
            stderr = stderr.decode()
        return ProcessResult(exitcode=exitcode, stdout=stdout, stderr=stderr, cmdline=cmd)

    @staticmethod
    def client_connectable(docker_client):
        try:
            if not docker_client.ping():
                return "The docker client failed to get a ping response from the docker daemon"
            return True
        except (APIError, RequestsConnectionError, PyWinTypesError) as exc:
            return "The docker client failed to ping the docker server: {}".format(exc)

    def run_container_start_checks(self, started_at, timeout_at):
        checks_start_time = time.time()
        while time.time() <= timeout_at:
            if not self.is_running():
                raise FactoryNotStarted("{} is no longer running".format(self))
            if self._container_start_checks():
                break
        else:
            log.error(
                "Failed to run container start checks after %1.2f seconds",
                time.time() - checks_start_time,
            )
            return False
        check_ports = set(self.get_check_ports())
        if not check_ports:
            return True
        while time.time() <= timeout_at:
            if not self.is_running():
                raise FactoryNotStarted("{} is no longer running".format(self))
            if not check_ports:
                break
            check_ports -= ports.get_connectable_ports(check_ports)
            if check_ports:
                time.sleep(0.5)
        else:
            log.error("Failed to check ports after %1.2f seconds", time.time() - checks_start_time)
            return False
        return True

    def _container_start_checks(self):
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
class SaltDaemonContainerFactory(SaltDaemonFactory, ContainerFactory):
    def __attrs_post_init__(self):
        self.daemon_started = self.daemon_starting = False
        if self.python_executable is None:
            # Default to whatever is the default python in the container
            self.python_executable = "python"
        SaltDaemonFactory.__attrs_post_init__(self)
        ContainerFactory.__attrs_post_init__(self)
        # There are some volumes which NEED to exist on the container so
        # that configs are in the right place and also our custom salt
        # plugins along with the custom scripts to start the daemons.
        root_dir = os.path.dirname(self.config["root_dir"])
        config_dir = str(self.config_dir)
        scripts_dir = str(self.factories_manager.scripts_dir)
        volumes = {
            root_dir: {"bind": root_dir, "mode": "z"},
            scripts_dir: {"bind": scripts_dir, "mode": "z"},
            config_dir: {"bind": self.config_dir, "mode": "z"},
            str(CODE_ROOT_DIR): {"bind": str(CODE_ROOT_DIR), "mode": "z"},
        }
        if "volumes" not in self.container_run_kwargs:
            self.container_run_kwargs["volumes"] = {}
        self.container_run_kwargs["volumes"].update(volumes)
        self.container_run_kwargs.setdefault("hostname", self.name)
        self.container_run_kwargs.setdefault("auto_remove", True)

    def build_cmdline(self, *args):
        return ["docker", "exec", "-i", self.name] + super().build_cmdline(*args)

    def start(self, *extra_cli_arguments, max_start_attempts=None, start_timeout=None):
        # Start the container
        ContainerFactory.start(
            self, max_start_attempts=max_start_attempts, start_timeout=start_timeout
        )
        self.daemon_starting = True
        # Now that the container is up, let's start the daemon
        self.daemon_started = SaltDaemonFactory.start(
            self,
            *extra_cli_arguments,
            max_start_attempts=max_start_attempts,
            start_timeout=start_timeout
        )
        return self.daemon_started

    def terminate(self):
        self.daemon_started = self.daemon_starting = False
        ret = SaltDaemonFactory.terminate(self)
        ContainerFactory.terminate(self)
        return ret

    def is_running(self):
        running = ContainerFactory.is_running(self)
        if running is False:
            return running
        if self.daemon_starting or self.daemon_started:
            return SaltDaemonFactory.is_running(self)
        return running

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        raise NotImplementedError


@attr.s(kw_only=True, slots=True)
class SaltMinionContainerFactory(SaltDaemonContainerFactory, SaltMinionFactory):
    """
    Salt minion daemon implementation running in a docker container
    """

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        return SaltMinionFactory.get_check_events(self)

    def run_start_checks(self, started_at, timeout_at):
        return SaltMinionFactory.run_start_checks(self, started_at, timeout_at)
