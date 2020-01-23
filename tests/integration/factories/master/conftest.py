# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals


def pytest_saltfactories_master_configuration_overrides(
    request, factories_manager, default_options, master_id
):
    """
    Hook which should return a dictionary tailored for the provided master_id.
    This dictionary will override the default_options dictionary.

    Stops at the first non None result
    """
    overrides = {"max_open_files": 4096}
    return overrides
