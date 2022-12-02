"""
Container based factories.
"""
import atexit
import contextlib
import logging
import os

import _pytest._version
import attr
import pytest
from pytestshellutils.customtypes import Callback
from pytestshellutils.exceptions import FactoryNotStarted
from pytestshellutils.shell import BaseFactory
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

    Args:
        :param str image:
            The container image to use, for example 'centos:7'
        :param str name:
            The name to give to the started container.
        :keyword dict check_ports:
            This dictionary is a mapping where the keys are the container port bindings and the
            values are the host port bindings.

            If this mapping is empty, the container class will inspect the
            :py:attr:`~saltfactories.daemons.container.Container.container_run_kwargs` for a
            ``ports`` key to build this mapping.

            Take as an example the following ``container_run_kwargs``:

            .. code-block:: python

                container_run_kwargs = {
                    "ports": {
                        "5000/tcp": None,
                        "12345/tcp": 54321,
                    }
                }

            This would build the following check ports mapping:

            .. code-block:: python

                {5000: None, 12345: 54321}

            At runtime, the :py:class:`~saltfactories.daemons.container.Container` class would query docker
            for the host port binding to the container port binding of 5000.

        :keyword dict container_run_kwargs:
            This mapping will be passed directly to the python docker library:

            .. code-block:: python

                container = self.docker_client.containers.run(
                    self.image,
                    name=self.name,
                    detach=True,
                    stdin_open=True,
                    command=list(command) or None,
                    **self.container_run_kwargs,
                )

        :keyword int start_timeout:
            The maximum number of seconds we should wait until the container is running.
        :keyword int max_start_attempts:
            The maximum number of attempts to try and start the container
        :keyword bool pull_before_start:
            When ``True``, the image is pulled before trying to start it
        :keyword bool skip_on_pull_failure:
            When ``True``, and there's a failure when pulling the image, the test is skipped.
        :keyword bool skip_if_docker_client_not_connectable:
            When ``True``, it skips the test if there's a failure when connecting to docker
        :keyword Docker docker_client:
            An instance of the python docker client to use.
            When nothing is passed, a default docker client is instantiated.
    """

    image = attr.ib()
    name = attr.ib()
    display_name = attr.ib(default=None)
    check_ports = attr.ib(default=attr.Factory(dict))
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
    _container_start_checks_callbacks = attr.ib(repr=False, hash=False, factory=list)
    _terminate_result = attr.ib(repr=False, hash=False, init=False, default=None)

    def __attrs_post_init__(self):
        """
        Post attrs initialization routines.
        """
        # Check that the docker client is connectable before starting
        self.before_start(self._check_for_connectable_docker_client)
        if self.pull_before_start:
            self.before_start(self._pull_container)

        # Register start check function
        self.container_start_check(self._check_listening_ports)

        if self.check_ports and not isinstance(self.check_ports, dict):
            check_ports = {}
            for port in self.check_ports:
                if not isinstance(port, tuple):
                    container_binding, host_binding = port, port
                check_ports[container_binding] = host_binding
            self.check_ports = check_ports

        if self.container_run_kwargs and "ports" in self.container_run_kwargs:
            _ports = self.container_run_kwargs["ports"]
            for container_binding, host_binding in _ports.items():
                port, proto = container_binding.split("/")
                if proto != "tcp":
                    continue
                if int(port) not in self.check_ports:
                    self.check_ports[int(port)] = host_binding

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
        self._before_start_callbacks.append(Callback(func=callback, args=args, kwargs=kwargs))

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
        self._after_start_callbacks.append(Callback(func=callback, args=args, kwargs=kwargs))

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
        self._before_terminate_callbacks.append(Callback(func=callback, args=args, kwargs=kwargs))

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

    def container_start_check(self, callback, *args, **kwargs):
        """
        Register a function to run after the container starts to confirm readiness for work.

        The callback must accept as the first argument ``timeout_at`` which is a float.
        The callback must stop trying to confirm running behavior once ``time.time() > timeout_at``.
        The callback should return ``True`` to confirm that the daemon is ready for work.

        For example:

        .. code-block:: python

            def check_running_state(timeout_at: float) -> bool:
                while time.time() <= timeout_at:
                    # run some checks
                    ...
                    # if all is good
                    break
                else:
                    return False
                return True

        :param ~collections.abc.Callable callback:
            The function to call back
        :keyword args:
            The arguments to pass to the callback
        :keyword kwargs:
            The keyword arguments to pass to the callback
        """
        self._container_start_checks_callbacks.append(
            Callback(func=callback, args=args, kwargs=kwargs)
        )

    def get_display_name(self):
        """
        Returns a human readable name for the factory.
        """
        if self.display_name is None:
            self.display_name = "{}(id={!r})".format(self.__class__.__name__, self.name)
        return self.display_name

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
        for callback in self._before_start_callbacks:
            try:
                callback()
            except Exception as exc:  # pragma: no cover pylint: disable=broad-except
                log.info(
                    "Exception raised when running %s: %s",
                    callback,
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
            for callback in self._after_start_callbacks:
                try:
                    callback()
                except Exception as exc:  # pragma: no cover pylint: disable=broad-except
                    log.info(
                        "Exception raised when running %s: %s",
                        callback,
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

    @contextlib.contextmanager
    def started(self, *command, max_start_attempts=None, start_timeout=None):
        """
        Start the container and return it's instance so it can be used as a context manager.
        """
        try:
            self.start(*command, max_start_attempts=max_start_attempts, start_timeout=start_timeout)
            yield self
        finally:
            self.terminate()

    def terminate(self):
        """
        Terminate the container.
        """
        if self._terminate_result is not None:
            # The factory is already terminated
            return self._terminate_result
        atexit.unregister(self.terminate)
        for callback in self._before_terminate_callbacks:
            try:
                callback()
            except Exception as exc:  # pragma: no cover pylint: disable=broad-except
                log.info(
                    "Exception raised when running %s: %s",
                    callback,
                    exc,
                    exc_info=True,
                )
        stdout = stderr = None
        try:
            if self.container is None:
                container = self.docker_client.containers.get(self.name)
            else:
                container = self.container
            self.container = None
            if container is not None:
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
                try:
                    container.remove(force=True)
                    container.wait()
                except APIError:
                    pass
        except NotFound:
            pass
        finally:
            for callback in self._after_terminate_callbacks:
                try:
                    callback()
                except Exception as exc:  # pragma: no cover pylint: disable=broad-except
                    log.info(
                        "Exception raised when running %s: %s",
                        callback,
                        exc,
                        exc_info=True,
                    )
        self._terminate_result = ProcessResult(returncode=0, stdout=stdout, stderr=stderr)
        return self._terminate_result

    def get_check_ports(self):
        """
        Return a list of TCP ports to check against to ensure the daemon is running.
        """
        _ports = self.check_ports.copy()
        if self.container:
            self.container.reload()
            for container_binding, host_binding in _ports.items():
                if isinstance(host_binding, int):
                    continue
                host_binding = self.get_host_port_binding(
                    container_binding, protocol="tcp", ipv6=False
                )
                if host_binding:
                    _ports[container_binding] = host_binding
        return _ports

    def get_host_port_binding(self, port, protocol="tcp", ipv6=False):
        """
        Return the host binding for a port on the container.

        Args:
            :keyword str protocol: The port protocol. Defaults to ``tcp``.
            :keyword bool ipv6:
                If true, return the ipv6 port binding.

        Returns:
            int: The matched port binding on the host.
            None: When not port binding was matched.
        """
        if self.container is None:
            return None
        _ports = self.container.ports
        log.debug("Container Ports for %s: %s", self, _ports)
        if not _ports:
            return None
        container_binding = "{}/{}".format(port, protocol)
        if container_binding not in _ports:
            return None
        host_port_bindings = _ports[container_binding]
        if not host_port_bindings:
            # This means the host is using the same port as the container
            return int(port)
        for host_binding_details in host_port_bindings:
            host_ip = host_binding_details["HostIp"]
            host_port = host_binding_details["HostPort"]
            if "::" in host_ip:
                if ipv6:
                    return int(host_port)
                continue
            return int(host_port)

    def get_container_start_check_callbacks(self):
        """
        Return a list of the start check callbacks.
        """
        return self._container_start_checks_callbacks or []

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

    def run_container_start_checks(
        self,
        started_at,  # pylint: disable=unused-argument
        timeout_at,
    ):
        """
        Run startup checks.
        """
        log.debug("Running container start checks...")
        start_check_callbacks = list(self.get_container_start_check_callbacks())
        if not start_check_callbacks:
            log.debug("No container start check callbacks to run for %s", self)
            return True
        checks_start_time = time.time()
        log.debug("%s is running container start checks", self)
        while time.time() <= timeout_at:
            if not self.is_running():
                raise FactoryNotStarted("{} is no longer running".format(self))
            if not start_check_callbacks:
                break
            start_check = start_check_callbacks[0]
            try:
                ret = start_check(timeout_at)
                if ret is True:
                    start_check_callbacks.pop(0)
            except Exception as exc:  # pylint: disable=broad-except
                log.info(
                    "Exception raised when running %s: %s",
                    start_check,
                    exc,
                    exc_info=True,
                )
        if start_check_callbacks:
            log.error(
                "Failed to run container start check callbacks after %1.2f seconds for %s. "
                "Remaining container start check callbacks: %s",
                time.time() - checks_start_time,
                self,
                start_check_callbacks,
            )
            return False
        log.debug("All container start check callbacks executed for %s", self)
        return True

    def _check_listening_ports(self, timeout_at: float) -> bool:
        """
        Check if the defined ports are in a listening state.

        This callback will run when trying to assess if the daemon is ready
        to accept work by trying to connect to each of the ports it's supposed
        to be listening.
        """
        check_ports_mapping = self.get_check_ports().copy()
        if not check_ports_mapping:
            log.debug("No ports to check connection to for %s", self)
            return True
        log.debug("Listening ports to check for %s: %s", self, check_ports_mapping)
        checks_start_time = time.time()
        check_ports = set(check_ports_mapping.values())
        while time.time() <= timeout_at:
            if not self.is_running():
                raise FactoryNotStarted("{} is no longer running".format(self))
            if not check_ports:
                break
            check_ports -= ports.get_connectable_ports(check_ports)
            if check_ports:
                for container_binding, host_binding in check_ports_mapping.copy().items():
                    if host_binding not in check_ports:
                        check_ports_mapping.pop(container_binding)
                time.sleep(0.5)
        else:
            log.error(
                "Failed to check ports after %1.2f seconds for %s. Remaining ports to check: %s",
                time.time() - checks_start_time,
                self,
                check_ports_mapping,
            )
            return False
        log.debug("All listening ports checked for %s: %s", self, self.get_check_ports())
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
class SaltDaemon(Container, bases.SaltDaemon):
    """
    Salt Daemon inside a container implementation.
    """

    _daemon_started = attr.ib(init=False, repr=False, default=False)
    _daemon_starting = attr.ib(init=False, repr=False, default=False)

    def __attrs_post_init__(self):
        """
        Post attrs initialization routines.
        """
        # Default to whatever is the default python in the container
        # and not the python_executable set by salt-factories
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
        log.debug("%s container_run_kwargs: %s", self, self.container_run_kwargs)

    def get_display_name(self):
        """
        Returns a human readable name for the factory.
        """
        return bases.SaltDaemon.get_display_name(self)

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
        running = Container.start(
            self, max_start_attempts=max_start_attempts, start_timeout=start_timeout
        )
        if not running:
            return running
        self._daemon_starting = True
        # Now that the container is up, let's start the daemon
        self._daemon_started = bases.SaltDaemon.start(
            self,
            *extra_cli_arguments,
            max_start_attempts=max_start_attempts,
            start_timeout=start_timeout,
        )
        return self._daemon_started

    def terminate(self):
        """
        Terminate the container.
        """
        self._daemon_started = self._daemon_starting = False
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
        if self._daemon_starting or self._daemon_started:
            return bases.SaltDaemon.is_running(self)
        return running

    def get_check_ports(self):
        """
        Return a list of ports to check against to ensure the daemon is running.
        """
        _ports = {port: port for port in bases.SaltDaemon.get_check_ports(self)}
        _ports.update(Container.get_check_ports(self))
        return _ports

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

    @contextlib.contextmanager
    def started(self, *extra_cli_arguments, max_start_attempts=None, start_timeout=None):
        """
        Start the daemon and return it's instance so it can be used as a context manager.
        """
        try:
            # Start the container
            with Container.started(
                self,
                *extra_cli_arguments,
                max_start_attempts=max_start_attempts,
                start_timeout=start_timeout,
            ):
                # Start the daemon
                with bases.SaltDaemon.started(
                    self,
                    *extra_cli_arguments,
                    max_start_attempts=max_start_attempts,
                    start_timeout=start_timeout,
                ):
                    yield self
        finally:
            self.terminate()

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

    def get_display_name(self):
        """
        Returns a human readable name for the factory.
        """
        return minion.SaltMinion.get_display_name(self)

    def get_check_events(self):
        """
        Return salt events to check.

        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        return minion.SaltMinion.get_check_events(self)
