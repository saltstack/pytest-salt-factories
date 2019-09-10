# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import 3rd-party libs
import pytest


@pytest.fixture
def master(request, salt_factories):
    return salt_factories.spawn_master(request, 'master-1')


def test_master(master):
    assert master.is_alive()
