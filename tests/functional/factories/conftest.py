# -*- coding: utf-8 -*-
"""
tests.functional.factories.conftest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import mock
import pytest

from saltfactories.factories import manager


@pytest.fixture
def salt_factories(
    request,
    pytestconfig,
    tempdir,
    log_server,
    log_server_port,
    log_server_level,
    salt_factories_config,
):
    with mock.patch("saltfactories.utils.event_listener.EventListener"):
        return manager.SaltFactoriesManager(
            pytestconfig,
            tempdir,
            log_server_port,
            log_server_level,
            stats_processes=request.session.stats_processes,
            **salt_factories_config
        )
