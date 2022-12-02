"""
Salt Daemon Factories PyTest Plugin.
"""
import logging
import os
import pathlib
import pprint

import pytest

import saltfactories
from saltfactories.manager import FactoriesManager

log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def _salt_factories_config(request):
    """
    Return a dictionary with the keyword arguments for FactoriesManager.
    """
    log_server = request.config.pluginmanager.get_plugin("saltfactories-log-server")
    return {
        "code_dir": saltfactories.CODE_ROOT_DIR.parent,
        "coverage_rc_path": saltfactories.CODE_ROOT_DIR.parent / ".coveragerc",
        "coverage_db_path": saltfactories.CODE_ROOT_DIR.parent / ".coverage",
        "inject_sitecustomize": True,
        "log_server_host": log_server.log_host,
        "log_server_port": log_server.log_port,
        "log_server_level": log_server.log_level,
        "system_service": (
            request.config.getoption("--system-service")
            or os.environ.get("SALT_FACTORIES_SYSTEM_SERVICE", "0") == "1"
        ),
        "python_executable": request.config.getoption("--python-executable"),
        "scripts_dir": request.config.getoption("--scripts-dir"),
    }


@pytest.fixture(scope="session")
def salt_factories_config():
    """
    Default salt factories configuration fixture.
    """
    return {}


@pytest.fixture(scope="session")
def salt_factories(
    tempdir,
    event_listener,
    stats_processes,
    salt_factories_config,  # pylint: disable=redefined-outer-name
    _salt_factories_config,
):
    """
    Instantiate the salt factories manager.
    """
    if not isinstance(salt_factories_config, dict):
        raise pytest.UsageError("The 'salt_factories_config' fixture MUST return a dictionary")
    if salt_factories_config:
        log.debug(
            "Salt Factories Manager Default Config:\n%s", pprint.pformat(_salt_factories_config)
        )
        log.debug("Salt Factories Manager User Config:\n%s", pprint.pformat(salt_factories_config))
    factories_config = _salt_factories_config.copy()
    factories_config.update(salt_factories_config)
    log.debug(
        "Instantiating the Salt Factories Manager with the following keyword arguments:\n%s",
        pprint.pformat(factories_config),
    )
    factories_config.setdefault("root_dir", tempdir)
    return FactoriesManager(
        stats_processes=stats_processes, event_listener=event_listener, **factories_config
    )


def pytest_addoption(parser):
    """
    Register argparse-style options and ini-style config values.
    """
    group = parser.getgroup("Salt Factories")
    group.addoption(
        "--system-service",
        default=False,
        action="store_true",
        help=(
            "Tell salt-factories to use the salt daemons system services, previously "
            "installed, instead of starting them from the available(and importable) "
            "salt checkout."
        ),
    )
    group.addoption(
        "--python-executable",
        default=None,
        help=(
            "Tell salt-factories which python executable should be used when it "
            "needs to prefix CLI commands with it. Defaults to `sys.executable`."
        ),
    )
    group.addoption(
        "--scripts-dir",
        default=None,
        type=pathlib.Path,
        help=(
            "Tell salt-factories where to look for the Salt daemon and CLI scripts. "
            "The several scripts to the Salt daemons and CLI's MUST exist. "
            "Passing this option will also make salt-factories NOT generate "
            "said scripts and set `python_executable` to `None`."
        ),
    )
