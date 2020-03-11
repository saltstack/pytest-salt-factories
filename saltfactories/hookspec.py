# -*- coding: utf-8 -*-
"""
saltfactories.hookspec
~~~~~~~~~~~~~~~~~~~~~~

Salt Factories Hooks
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import pytest


@pytest.hookspec(firstresult=True)
def pytest_saltfactories_generate_default_minion_configuration(
    request, factories_manager, root_dir, minion_id, master_port
):
    """
    Hook which should return a dictionary tailored for the provided minion_id

    Stops at the first non None result
    """


@pytest.hookspec(firstresult=True)
def pytest_saltfactories_minion_configuration_overrides(
    request, factories_manager, root_dir, minion_id, default_options
):
    """
    Hook which should return a dictionary tailored for the provided minion_id.
    This dictionary will override the default_options dictionary.

    Stops at the first non None result
    """


def pytest_saltfactories_verify_minion_configuration(request, minion_config, username):
    """
    This hook is called to vefiry the provided minion configuration
    """


@pytest.hookspec(firstresult=True)
def pytest_saltfactories_write_minion_configuration(request, minion_config):
    """
    This hook is called to write the provided minion configuration
    """


@pytest.hookspec(firstresult=True)
def pytest_saltfactories_generate_default_master_configuration(
    request, factories_manager, root_dir, master_id, order_masters
):
    """
    Hook which should return a dictionary tailored for the provided master_id

    Stops at the first non None result
    """


@pytest.hookspec(firstresult=True)
def pytest_saltfactories_master_configuration_overrides(
    request, factories_manager, root_dir, master_id, default_options, order_masters
):
    """
    Hook which should return a dictionary tailored for the provided master_id.
    This dictionary will override the default_options dictionary.

    Stops at the first non None result
    """


def pytest_saltfactories_verify_master_configuration(request, master_config, username):
    """
    This hook is called to vefiry the provided master configuration
    """


@pytest.hookspec(firstresult=True)
def pytest_saltfactories_write_master_configuration(request, master_config):
    """
    This hook is called to write the provided master configuration
    """


@pytest.hookspec(firstresult=True)
def pytest_saltfactories_generate_default_syndic_configuration(
    request, factories_manager, root_dir, syndic_id, syndic_master_port
):
    """
    Hook which should return a dictionary tailored for the provided syndic_id with 3 keys:

    * `master`: The default config for the master running along with the syndic
    * `minion`: The default config for the master running along with the syndic
    * `syndic`: The default config for the master running along with the syndic

    Stops at the first non None result
    """


@pytest.hookspec(firstresult=True)
def pytest_saltfactories_syndic_configuration_overrides(
    request, factories_manager, root_dir, syndic_id, default_options
):
    """
    Hook which should return a dictionary tailored for the provided syndic_id.
    This dictionary will override the default_options dictionary.

    The returned dictionary should contain 3 keys:

    * `master`: The config overrides for the master running along with the syndic
    * `minion`: The config overrides for the master running along with the syndic
    * `syndic`: The config overridess for the master running along with the syndic

    The `default_options` parameter be None or have 3 keys, `master`, `minion`, `syndic`,
    while will contain the default options for each of the daemons.

    Stops at the first non None result
    """


def pytest_saltfactories_verify_syndic_configuration(request, syndic_config, username):
    """
    This hook is called to vefiry the provided syndic configuration
    """


@pytest.hookspec(firstresult=True)
def pytest_saltfactories_write_syndic_configuration(request, syndic_config):
    """
    This hook is called to write the provided syndic configuration
    """


@pytest.hookspec(firstresult=True)
def pytest_saltfactories_generate_default_proxy_minion_configuration(
    request, factories_manager, root_dir, proxy_minion_id, master_port
):
    """
    Hook which should return a dictionary tailored for the provided proxy_minion_id

    Stops at the first non None result
    """


@pytest.hookspec(firstresult=True)
def pytest_saltfactories_proxy_minion_configuration_overrides(
    request, factories_manager, root_dir, proxy_minion_id, default_options
):
    """
    Hook which should return a dictionary tailored for the provided proxy_minion_id.
    This dictionary will override the default_options dictionary.

    Stops at the first non None result
    """


def pytest_saltfactories_verify_proxy_minion_configuration(request, proxy_minion_config, username):
    """
    This hook is called to vefiry the provided proxy_minion configuration
    """


@pytest.hookspec(firstresult=True)
def pytest_saltfactories_write_proxy_minion_configuration(request, proxy_minion_config):
    """
    This hook is called to write the provided proxy_minion configuration
    """
