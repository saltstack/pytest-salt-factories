"""
Container based factories.

..
    PYTEST_DONT_REWRITE
"""
import atexit
import logging
import os

import _pytest._version
import attr
import pytest
from pytestshellutils.exceptions import FactoryNotStarted
from pytestshellutils.shell import BaseFactory
from pytestshellutils.utils import format_callback_to_string
from pytestshellutils.utils import ports
from pytestshellutils.utils import time
from pytestshellutils.utils.processes import ProcessResult

from saltfactories import bases
from saltfactories import CODE_ROOT_DIR
from saltfactories.daemons import minion
from saltfactories.utils import random_string

try:
    import docker
    from docker.errors import DockerException, APIError, NotFound

    HAS_DOCKER = True
except ImportError:  # pragma: no cover
    HAS_DOCKER = False

    class DockerException(Exception):
        """
        Define DockerException to avoid NameError.
        """

    class APIError(Exception):
        """
        Define APIError to avoid NameError.
        """

    class NotFound(Exception):
        """
        Define NotFound to avoid NameError.
        """


try:
    from requests.exceptions import ConnectionError as RequestsConnectionError

    HAS_REQUESTS = True
except ImportError:  # pragma: no cover
    HAS_REQUESTS = False

    class RequestsConnectionError(ConnectionError):
        """
        Define RequestsConnectionError to avoid NameError.
        """


try:
    import pywintypes

    PyWinTypesError = pywintypes.error  # pragma: no cover
except ImportError:

    class PyWinTypesError(Exception):
        """
        Define PyWinTypesError to avoid NameError.
        """


log = logging.getLogger(__name__)

PYTEST_GE_7 = getattr(_pytest._version, "version_tuple", (-1, -1)) >= (7, 0)


@attr.s(kw_only=True)
class Container(BaseFactory):
    """
    Docker containers daemon implementation.
    """

    image = attr.ib()
    name = attr.ib()
    display_name = attr.ib(default=None)
    check_ports = attr.ib(default=None)
    container_run_kwargs = attr.ib(repr=False, default=attr.Factory(dict))
    container = attr.ib(init=False, default=None, repr=False)
    start_timeout = attr.ib(repr=False, default=30)
    max_start_attempts = attr.ib(repr=False, default=3)
    pull_before_start = attr.ib(repr=False, default=True)
    skip_on_pull_failure = attr.ib(repr=False, default=False)
    skip_if_docker_client_not_connectable = attr.ib(repr=False, default=False)
    docker_client = attr.ib(repr=False)
    _before_start_callbacks = attr.ib(repr=False, hash=False, default=attr.Factory(list))
    _before_terminate_callbacks = attr.ib(repr=False, hash=False, default=attr.Factory(list))
    _after_start_callbacks = attr.ib(repr=False, hash=False, default=attr.Factory(list))
    _after_terminate_callbacks = attr.ib(repr=False, hash=False, default=attr.Factory(list))
    _terminate_result = attr.ib(repr=False, hash=False, init=False, default=None)

    def __attrs_post_init__(self):
        """
        Post attrs initialization routines.
        """
        # Check that the docker client is connectable before starting
        self.before_start(self._check_for_connectable_docker_client)
        if self.pull_before_start:
            self.before_start(self._pull_container)

    @name.default
    def _default_name(self):
        return random_string("factories-")

    @docker_client.default
    def _default_docker_client(self):
        exc_kwargs = {}
        if PYTEST_GE_7:
            exc_kwargs["_use_item_location"] = True
        if not HAS_DOCKER:
            message = "The docker python library was not found installed"
            if self.skip_if_docker_client_not_connectable:
                raise pytest.skip.Exception(message, **exc_kwargs)
            else:
                pytest.fail(message)
        if not HAS_REQUESTS:
            message = "The requests python library was not found installed"
            if self.skip_if_docker_client_not_connectable:
                raise pytest.skip.Exception(message, **exc_kwargs)
            else:
                pytest.fail(message)
        try:
            docker_client = docker.from_env()
        except DockerException as exc:
            message = "Failed to instantiate the docker client: {}".format(exc)
            if self.skip_if_docker_client_not_connectable:
                raise pytest.skip.Exception(message, **exc_kwargs) from exc
            else:
                pytest.fail(message)
        else:
            return docker_client

    def before_start(self, callback, *args, **kwargs):
        """
        Register a function callback to run before the container starts.

        :param ~collections.abc.Callable callback:
            The function to call back
        :keyword args:
            The arguments to pass to the callback
        :keyword kwargs:
            The keyword arguments to pass to the callback
        """
        self._before_start_callbacks.append((callback, args, kwargs))

    def after_start(self, callback, *args, **kwargs):
        """
        Register a function callback to run after the container starts.

        :param ~collections.abc.Callable callback:
            The function to call back
        :keyword args:
            The arguments to pass to the callback
        :keyword kwargs:
            The keyword arguments to pass to the callback
        """
        self._after_start_callbacks.append((callback, args, kwargs))

    def before_terminate(self, callback, *args, **kwargs):
        """
        Register a function callback to run before the container terminates.

        :param ~collections.abc.Callable callback:
            The function to call back
        :keyword args:
            The arguments to pass to the callback
        :keyword kwargs:
            The keyword arguments to pass to the callback
        """
        self._before_terminate_callbacks.append((callback, args, kwargs))

    def after_terminate(self, callback, *args, **kwargs):
        """
        Register a function callback to run after the container terminates.

        :param ~collections.abc.Callable callback:
            The function to call back
        :keyword args:
            The arguments to pass to the callback
        :keyword kwargs:
            The keyword arguments to pass to the callback
        """
        self._after_terminate_callbacks.append((callback, args, kwargs))

    def get_display_name(self):
        """
        Returns a human readable name for the factory.
        """
        if self.display_name is None:
            self.display_name = "{}(id={!r})".format(self.__class__.__name__, self.id)
        return super().get_display_name()

    def start(self, *command, max_start_attempts=None, start_timeout=None):
        """
        Start the container.
        """
        if self.is_running():
            log.warning("%s is already running.", self)
            return True
        self._terminate_result = None
        atexit.register(self.terminate)
        factory_started = False
        for callback, args, kwargs in self._before_start_callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as exc:  # pragma: no cover pylint: disable=broad-except
                log.info(
                    "Exception raised when running %s: %s",
                    format_callback_to_string(callback, args, kwargs),
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
                **self.container_run_kwargs,
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
                except APIError:
                    pass
                self.container = None
        else:
            # The factory failed to confirm it's running status
            self.terminate()
        if factory_started:
            for callback, args, kwargs in self._after_start_callbacks:
                try:
                    callback(*args, **kwargs)
                except Exception as exc:  # pragma: no cover pylint: disable=broad-except
                    log.info(
                        "Exception raised when running %s: %s",
                        format_callback_to_string(callback, args, kwargs),
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
            process_result=result,
        )

    def started(self, *command, max_start_attempts=None, start_timeout=None):
        """
        Start the container and return it's instance so it can be used as a context manager.
        """
        self.start(*command, max_start_attempts=max_start_attempts, start_timeout=start_timeout)
        return self

    def terminate(self):
        """
        Terminate the container.
        """
        if self._terminate_result is not None:
            # The factory is already terminated
            return self._terminate_result
        atexit.unregister(self.terminate)
        for callback, args, kwargs in self._before_terminate_callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as exc:  # pragma: no cover pylint: disable=broad-except
                log.info(
                    "Exception raised when running %s: %s",
                    format_callback_to_string(callback, args, kwargs),
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
                    try:
                        self.container.remove(force=True)
                        self.container.wait()
                    except APIError:
                        pass
                self.container = None
        except NotFound:
            pass
        finally:
            for callback, args, kwargs in self._after_terminate_callbacks:
                try:
                    callback(*args, **kwargs)
                except Exception as exc:  # pragma: no cover pylint: disable=broad-except
                    log.info(
                        "Exception raised when running %s: %s",
                        format_callback_to_string(callback, args, kwargs),
                        exc,
                        exc_info=True,
                    )
        self._terminate_result = ProcessResult(returncode=0, stdout=stdout, stderr=stderr)
        return self._terminate_result

    def get_check_ports(self):
        """
        Return a list of ports to check against to ensure the daemon is running.
        """
        return self.check_ports or []

    def is_running(self):
        """
        Returns true if the container is running.
        """
        if self.container is None:
            return False

        self.container = self.docker_client.containers.get(self.name)
        return self.container.status == "running"

    def run(self, *cmd, **kwargs):
        """
        Run a command inside the container.
        """
        if len(cmd) == 1:
            cmd = cmd[0]
        log.info("%s is running %r ...", self, cmd)
        # We force dmux to True so that we always get back both stdout and stderr
        container = self.docker_client.containers.get(self.name)
        ret = container.exec_run(cmd, demux=True, **kwargs)
        returncode = ret.exit_code
        stdout = stderr = None
        if ret.output:
            stdout, stderr = ret.output
        if stdout is not None:
            stdout = stdout.decode()
        if stderr is not None:
            stderr = stderr.decode()
        return ProcessResult(returncode=returncode, stdout=stdout, stderr=stderr, cmdline=cmd)

    @staticmethod
    def client_connectable(docker_client):
        """
        Check if the docker client can connect to the docker daemon.
        """
        try:
            if not docker_client.ping():
                return "The docker client failed to get a ping response from the docker daemon"
            return True
        except (APIError, RequestsConnectionError, PyWinTypesError) as exc:
            return "The docker client failed to ping the docker server: {}".format(exc)

    def run_container_start_checks(self, started_at, timeout_at):
        """
        Run startup checks.
        """
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

    def _check_for_connectable_docker_client(self):
        connectable = Container.client_connectable(self.docker_client)
        if connectable is not True:
            if self.skip_if_docker_client_not_connectable:
                exc_kwargs = {}
                if PYTEST_GE_7:
                    exc_kwargs["_use_item_location"] = True
                raise pytest.skip.Exception(connectable, **exc_kwargs)
            else:
                pytest.fail(connectable)

    def _pull_container(self):
        connectable = Container.client_connectable(self.docker_client)
        if connectable is not True:
            pytest.fail(connectable)
        log.info("Pulling docker image '%s' before starting it", self.image)
        try:
            self.docker_client.images.pull(self.image)
        except APIError as exc:
            if self.skip_on_pull_failure:
                exc_kwargs = {}
                if PYTEST_GE_7:
                    exc_kwargs["_use_item_location"] = True
                raise pytest.skip.Exception(
                    "Failed to pull docker image '{}': {}".format(
                        self.image,
                        exc,
                    ),
                    **exc_kwargs,
                ) from exc
            raise

    def __enter__(self):
        """
        Use as a context manager.
        """
        if not self.is_running():
            raise RuntimeError(
                "Factory not yet started. Perhaps you're after something like:\n\n"
                "with {}.started() as factory:\n"
                "    yield factory".format(self.__class__.__name__)
            )
        return self

    def __exit__(self, *_):
        """
        Exit context manager.
        """
        self.terminate()


@attr.s(kw_only=True)
class SaltDaemon(bases.SaltDaemon, Container):
    """
    Salt Daemon inside a container implementation.
    """

    def __attrs_post_init__(self):
        """
        Post attrs initialization routines.
        """
        self.daemon_started = self.daemon_starting = False
        if self.python_executable is None:
            # Default to whatever is the default python in the container
            self.python_executable = "python"
        bases.SaltDaemon.__attrs_post_init__(self)
        Container.__attrs_post_init__(self)
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
        self.container_run_kwargs.setdefault("remove", True)
        self.container_run_kwargs.setdefault("auto_remove", True)

    def run(self, *cmd, **kwargs):
        """
        Run a command inside the container.
        """
        return Container.run(self, *cmd, **kwargs)

    def cmdline(self, *args):
        """
        Construct a list of arguments to use when starting the container.

        :param str args:
            Additional arguments to use when starting the container

        """
        return ["docker", "exec", "-i", self.name] + super().cmdline(*args)

    def start(self, *extra_cli_arguments, max_start_attempts=None, start_timeout=None):
        """
        Start the daemon.
        """
        # Start the container
        Container.start(self, max_start_attempts=max_start_attempts, start_timeout=start_timeout)
        self.daemon_starting = True
        # Now that the container is up, let's start the daemon
        self.daemon_started = bases.SaltDaemon.start(
            self,
            *extra_cli_arguments,
            max_start_attempts=max_start_attempts,
            start_timeout=start_timeout,
        )
        return self.daemon_started

    def terminate(self):
        """
        Terminate the container.
        """
        self.daemon_started = self.daemon_starting = False
        ret = bases.SaltDaemon.terminate(self)
        Container.terminate(self)
        return ret

    def is_running(self):
        """
        Returns true if the container is running.
        """
        running = Container.is_running(self)
        if running is False:
            return running
        if self.daemon_starting or self.daemon_started:
            return bases.SaltDaemon.is_running(self)
        return running

    def get_check_ports(self):
        """
        Return a list of ports to check against to ensure the daemon is running.
        """
        return Container.get_check_ports(self) + bases.SaltDaemon.get_check_ports(self)

    def before_start(
        self, callback, *args, on_container=False, **kwargs
    ):  # pylint: disable=arguments-differ
        """
        Register a function callback to run before the daemon starts.

        :param ~collections.abc.Callable callback:
            The function to call back
        :keyword bool on_container:
            If true, the callback will be registered on the container and not the daemon.
        :keyword args:
            The arguments to pass to the callback
        :keyword kwargs:
            The keyword arguments to pass to the callback
        """
        if on_container:
            Container.before_start(self, callback, *args, **kwargs)
        else:
            bases.SaltDaemon.before_start(self, callback, *args, **kwargs)

    def after_start(
        self, callback, *args, on_container=False, **kwargs
    ):  # pylint: disable=arguments-differ
        """
        Register a function callback to run after the daemon starts.

        :param ~collections.abc.Callable callback:
            The function to call back
        :keyword bool on_container:
            If true, the callback will be registered on the container and not the daemon.
        :keyword args:
            The arguments to pass to the callback
        :keyword kwargs:
            The keyword arguments to pass to the callback
        """
        if on_container:
            Container.after_start(self, callback, *args, **kwargs)
        else:
            bases.SaltDaemon.after_start(self, callback, *args, **kwargs)

    def before_terminate(
        self, callback, *args, on_container=False, **kwargs
    ):  # pylint: disable=arguments-differ
        """
        Register a function callback to run before the daemon terminates.

        :param ~collections.abc.Callable callback:
            The function to call back
        :keyword bool on_container:
            If true, the callback will be registered on the container and not the daemon.
        :keyword args:
            The arguments to pass to the callback
        :keyword kwargs:
            The keyword arguments to pass to the callback
        """
        if on_container:
            Container.before_terminate(self, callback, *args, **kwargs)
        else:
            bases.SaltDaemon.before_terminate(self, callback, *args, **kwargs)

    def after_terminate(
        self, callback, *args, on_container=False, **kwargs
    ):  # pylint: disable=arguments-differ
        """
        Register a function callback to run after the daemon terminates.

        :param ~collections.abc.Callable callback:
            The function to call back
        :keyword bool on_container:
            If true, the callback will be registered on the container and not the daemon.
        :keyword args:
            The arguments to pass to the callback
        :keyword kwargs:
            The keyword arguments to pass to the callback
        """
        if on_container:
            Container.after_terminate(self, callback, *args, **kwargs)
        else:
            bases.SaltDaemon.after_terminate(self, callback, *args, **kwargs)

    def started(self, *extra_cli_arguments, max_start_attempts=None, start_timeout=None):
        """
        Start the daemon and return it's instance so it can be used as a context manager.
        """
        return bases.SaltDaemon.started(
            self,
            *extra_cli_arguments,
            max_start_attempts=max_start_attempts,
            start_timeout=start_timeout,
        )

    def get_check_events(self):
        """
        Return salt events to check.

        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        raise NotImplementedError


@attr.s(kw_only=True, slots=True)
class SaltMinion(SaltDaemon, minion.SaltMinion):
    """
    Salt minion daemon implementation running in a docker container.
    """

    def get_check_events(self):
        """
        Return salt events to check.

        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        return minion.SaltMinion.get_check_events(self)

    def run_start_checks(self, started_at, timeout_at):
        """
        Run checks to confirm that the container has started.
        """
        return minion.SaltMinion.run_start_checks(self, started_at, timeout_at)
