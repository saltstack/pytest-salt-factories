# -*- coding: utf-8 -*-
"""
saltfactories.plugin
~~~~~~~~~~~~~~~~~~~~

Salt Factories PyTest plugin interface
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import pprint
import sys
import tempfile

import pytest
import salt.config
import salt.loader  # pylint: disable=unused-import
import salt.utils.verify as salt_verify
import salt.utils.yaml as yamlserialize

from saltfactories import hookspec
from saltfactories.factories import manager
from saltfactories.utils import compat
from saltfactories.utils import ports
from saltfactories.utils.log_server import log_server_listener


log = logging.getLogger(__name__)


def pytest_addhooks(pluginmanager):
    """
    Register our custom hooks
    """
    pluginmanager.add_hookspecs(hookspec)


def pytest_tempdir_temproot():
    # Taken from https://github.com/saltstack/salt/blob/v2019.2.0/tests/support/paths.py
    # Avoid ${TMPDIR} and gettempdir() on MacOS as they yield a base path too long
    # for unix sockets: ``error: AF_UNIX path too long``
    # Gentoo Portage prefers ebuild tests are rooted in ${TMPDIR}
    if not sys.platform.startswith("darwin"):
        tempdir = os.environ.get("TMPDIR") or tempfile.gettempdir()
    else:
        tempdir = "/tmp"
    return os.path.abspath(os.path.realpath(tempdir))


def pytest_tempdir_basename():
    """
    Return the temporary directory basename for the salt test suite.
    """
    return "saltfactories"


@pytest.fixture(scope="session")
def log_server_port(request):
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
def log_server(log_server_port):
    log.info("Starting log server")
    with log_server_listener(log_server_port):
        log.info("Log Server Started")
        # Run tests
        yield


@pytest.fixture(scope="session")
def salt_factories(pytestconfig, tempdir, log_server, log_server_port, log_server_level):
    return manager.SaltFactoriesManager(pytestconfig, tempdir, log_server_port, log_server_level)


def pytest_saltfactories_verify_minion_configuration(request, minion_config, username):
    """
    This hook is called to vefiry the provided minion configuration
    """
    # verify env to make sure all required directories are created and have the
    # right permissions
    verify_env_entries = [
        os.path.join(minion_config["pki_dir"], "minions"),
        os.path.join(minion_config["pki_dir"], "minions_pre"),
        os.path.join(minion_config["pki_dir"], "minions_rejected"),
        os.path.join(minion_config["pki_dir"], "accepted"),
        os.path.join(minion_config["pki_dir"], "rejected"),
        os.path.join(minion_config["pki_dir"], "pending"),
        os.path.dirname(minion_config["log_file"]),
        os.path.join(minion_config["cachedir"], "proc"),
        # minion_config['extension_modules'],
        minion_config["sock_dir"],
    ]
    salt_verify.verify_env(verify_env_entries, username, pki_dir=minion_config["pki_dir"])


def pytest_saltfactories_write_minion_configuration(request, minion_config):
    """
    This hook is called to vefiry the provided minion configuration
    """
    config_file = minion_config.pop("conf_file")
    log.debug(
        "Writing to configuration file %s. Configuration:\n%s",
        config_file,
        pprint.pformat(minion_config),
    )

    # Write down the computed configuration into the config file
    with compat.fopen(config_file, "w") as wfh:
        yamlserialize.safe_dump(minion_config, wfh, default_flow_style=False)

    # Make sure to load the config file as a salt-master starting from CLI
    options = salt.config.minion_config(
        config_file, minion_id=minion_config["id"], cache_minion_id=True
    )
    return options


def pytest_saltfactories_verify_master_configuration(request, master_config, username):
    """
    This hook is called to vefiry the provided master configuration
    """
    # verify env to make sure all required directories are created and have the
    # right permissions
    verify_env_entries = [
        os.path.join(master_config["pki_dir"], "minions"),
        os.path.join(master_config["pki_dir"], "minions_pre"),
        os.path.join(master_config["pki_dir"], "minions_rejected"),
        os.path.join(master_config["pki_dir"], "accepted"),
        os.path.join(master_config["pki_dir"], "rejected"),
        os.path.join(master_config["pki_dir"], "pending"),
        os.path.dirname(master_config["log_file"]),
        os.path.join(master_config["cachedir"], "proc"),
        # master_config['extension_modules'],
        master_config["sock_dir"],
    ]
    verify_env_entries += master_config["file_roots"]["base"]
    verify_env_entries += master_config["file_roots"]["prod"]
    verify_env_entries += master_config["pillar_roots"]["base"]
    verify_env_entries += master_config["pillar_roots"]["prod"]

    if master_config.get("transport", None) == "raet":
        verify_env_entries.extend([os.path.join(master_config["cachedir"], "raet")])
    else:
        verify_env_entries.extend([os.path.join(master_config["cachedir"], "jobs")])
    salt_verify.verify_env(verify_env_entries, username, pki_dir=master_config["pki_dir"])


def pytest_saltfactories_write_master_configuration(request, master_config):
    """
    This hook is called to vefiry the provided master configuration
    """
    config_file = master_config.pop("conf_file")
    log.debug(
        "Writing to configuration file %s. Configuration:\n%s",
        config_file,
        pprint.pformat(master_config),
    )

    # Write down the computed configuration into the config file
    with compat.fopen(config_file, "w") as wfh:
        yamlserialize.safe_dump(master_config, wfh, default_flow_style=False)

    # Make sure to load the config file as a salt-master starting from CLI
    options = salt.config.master_config(config_file)
    return options


def pytest_saltfactories_verify_syndic_configuration(request, syndic_config, username):
    """
    This hook is called to vefiry the provided syndic configuration
    """
    # verify env to make sure all required directories are created and have the
    # right permissions
    verify_env_entries = [
        os.path.dirname(syndic_config["syndic_log_file"]),
    ]
    salt_verify.verify_env(
        verify_env_entries, username,
    )


def pytest_saltfactories_write_syndic_configuration(request, syndic_config):
    """
    This hook is called to vefiry the provided syndic configuration
    """
    config_file = syndic_config.pop("conf_file")
    log.debug(
        "Writing to configuration file %s. Configuration:\n%s",
        config_file,
        pprint.pformat(syndic_config),
    )

    # Write down the computed configuration into the config file
    with compat.fopen(config_file, "w") as wfh:
        yamlserialize.safe_dump(syndic_config, wfh, default_flow_style=False)

    conf_dir = os.path.dirname(os.path.dirname(config_file))
    master_config_file = os.path.join(conf_dir, "master")
    minion_config_file = os.path.join(conf_dir, "minion")

    # Make sure to load the config file as a salt-master starting from CLI
    options = salt.config.syndic_config(master_config_file, minion_config_file)
    return options
