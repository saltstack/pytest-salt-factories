# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import pytest


@pytest.fixture
def master(request, salt_factories):
    return salt_factories.spawn_master(request, "master-1")


def test_master(master):
    assert master.is_alive()
