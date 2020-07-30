"""
tests.functional.factories.conftest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""
from unittest import mock

import pytest

from saltfactories.factories import manager


@pytest.fixture
def salt_factories(
    request, pytestconfig, tempdir, log_server, salt_factories_config,
):
    with mock.patch("saltfactories.utils.event_listener.EventListener"):
        return manager.FactoriesManager(
            pytestconfig=pytestconfig,
            root_dir=tempdir,
            stats_processes=request.session.stats_processes,
            **salt_factories_config
        )
