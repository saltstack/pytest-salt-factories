"""
..
    PYTEST_DONT_REWRITE


saltfactories.plugins.factories
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Salt Daemon Factories PyTest Plugin
"""
import logging
import pprint

import pytest

import saltfactories
from saltfactories import hookspec
from saltfactories.factories import manager
from saltfactories.utils import ports
from saltfactories.utils.log_server import log_server_listener


log = logging.getLogger(__name__)


def pytest_addhooks(pluginmanager):
    """
    Register our custom hooks
    """
    pluginmanager.add_hookspecs(hookspec)


@pytest.fixture(scope="session")
def log_server_host():
    return "0.0.0.0"


@pytest.fixture(scope="session")
def log_server_port():
    return ports.get_unused_localhost_port()


@pytest.fixture(scope="session")
def log_server_level(request):
    # If PyTest has no logging configured, default to ERROR level
    levels = [logging.ERROR]
    logging_plugin = request.config.pluginmanager.get_plugin("logging-plugin")
    try:
        level = logging_plugin.log_cli_handler.level
        if level is not None:
            levels.append(level)
    except AttributeError:
        # PyTest CLI logging not configured
        pass
    try:
        level = logging_plugin.log_file_level
        if level is not None:
            levels.append(level)
    except AttributeError:
        # PyTest Log File logging not configured
        pass

    level_str = logging.getLevelName(min(levels))
    return level_str


@pytest.fixture(scope="session")
def log_server(log_server_host, log_server_port):
    log.info("Starting log server at %s:%d", log_server_host, log_server_port)
    with log_server_listener(log_server_host, log_server_port):
        log.info("Log Server Started")
        # Run tests
        yield


@pytest.fixture(scope="session")
def salt_factories_config(
    pytestconfig, tempdir, log_server_host, log_server_port, log_server_level
):
    """
    Return a dictionary with the keyword arguments for FactoriesManager
    """
    return {
        "code_dir": saltfactories.CODE_ROOT_DIR.parent,
        "inject_coverage": True,
        "inject_sitecustomize": True,
        "log_server_host": log_server_host,
        "log_server_port": log_server_port,
        "log_server_level": log_server_level,
    }


@pytest.fixture(scope="session")
def salt_factories(
    request, pytestconfig, tempdir, log_server, salt_factories_config,
):
    if not isinstance(salt_factories_config, dict):
        raise RuntimeError("The 'salt_factories_config' fixture MUST return a dictionary")
    log.debug(
        "Instantiating the Salt Factories Manager with the following keyword arguments:\n%s",
        pprint.pformat(salt_factories_config),
    )
    _manager = manager.FactoriesManager(
        pytestconfig=pytestconfig,
        root_dir=tempdir,
        stats_processes=request.session.stats_processes,
        **salt_factories_config
    )
    yield _manager
    _manager.event_listener.stop()


def pytest_saltfactories_handle_key_auth_event(
    factories_manager, master_id, minion_id, keystate, payload
):
    """
    This hook is called for every auth event on the masters
    """
    salt_key_cli = factories_manager.get_salt_key_cli(master_id)
    if keystate == "pend":
        ret = salt_key_cli.run("--yes", "--accept", minion_id)
        assert ret.exitcode == 0
