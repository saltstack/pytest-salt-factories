"""
    saltfactories.factories.daemons.docker
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Docker based factories
"""
import atexit
import logging
import time

import attr
import pytest

from saltfactories.exceptions import FactoryNotStarted
from saltfactories.factories.base import Factory
from saltfactories.utils import random_string
from saltfactories.utils.processes import ProcessResult

try:
    import docker
    from docker.exceptions import APIError
    from requests.exceptions import ConnectionError as RequestsConnectionError

    HAS_DOCKER = True
except ImportError:
    HAS_DOCKER = False

    class APIError(Exception):
        pass

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
class DockerFactory(Factory):
    image = attr.ib()
    name = attr.ib(default=None)
    check_ports = attr.ib(default=None)
    docker_client = attr.ib(repr=False, default=None)
    container_run_kwargs = attr.ib(repr=False, default=attr.Factory(dict))
    container = attr.ib(init=False, default=None, repr=False)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.name is None:
            self.name = random_string("factories-")
        if self.docker_client is None:
            if not HAS_DOCKER:
                pytest.fail("The docker python library was not found installed")
            self.docker_client = docker.from_env()

    def start(self):
        atexit.register(self.terminate)
        connectable = DockerFactory.client_connectable(self.docker_client)
        if connectable is not True:
            pytest.fail(connectable)
        start_time = time.time()
        start_timeout = start_time + 30
        # image = self.docker_client.images.pull(self.image)
        self.container = self.docker_client.containers.run(
            self.image, name=self.name, detach=True, stdin_open=True, **self.container_run_kwargs
        )
        while True:
            if start_timeout <= time.time():
                result = self.terminate()
                raise FactoryNotStarted(
                    "Container failed to start",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    exitcode=result.exitcode,
                )
            container = self.docker_client.containers.get(self.container.id)
            if container.status == "running":
                self.container = container
                break
            time.sleep(1)

    def terminate(self):
        atexit.unregister(self.terminate)
        stdout = stderr = None
        if self.container is None:
            return ProcessResult(exitcode=0, stdout=None, stderr=None)
        try:
            container = self.docker_client.containers.get(self.container.id)
            logs = container.logs(stdout=True, stderr=True, stream=False)
            if isinstance(logs, bytes):
                stdout = logs.decode()
            else:
                stdout = logs[0].decode()
                stderr = logs[1].decode()
            log.warning("Running Container Logs:\n%s\n%s", stdout, stderr)
            if container.status == "running":
                container.remove(force=True)
                container.wait()
        except docker.errors.NotFound:
            pass
        return ProcessResult(exitcode=0, stdout=stdout, stderr=stderr)

    def get_check_ports(self):
        """
        Return a list of ports to check against to ensure the daemon is running
        """
        return self.check_ports or []

    def is_running(self):
        return self.container.status == "running"

    def run(self, *cmd, **kwargs):
        if len(cmd) == 1:
            cmd = cmd[0]
        log.info("%sRunning %r ...", self.get_log_prefix(), cmd)
        # We force dmux to True so that we always get back both stdout and stderr
        ret = self.container.exec_run(cmd, demux=True, **kwargs)
        exitcode = ret.exit_code
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
