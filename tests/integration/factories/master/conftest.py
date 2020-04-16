# -*- coding: utf-8 -*-


def pytest_saltfactories_master_configuration_overrides(
    request, factories_manager, config_defaults, master_id
):
    """
    Hook which should return a dictionary tailored for the provided master_id.
    This dictionary will override the config_defaults dictionary.

    Stops at the first non None result
    """
    overrides = {"max_open_files": 4096}
    return overrides
