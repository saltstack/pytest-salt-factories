# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import 3rd-party libs
import pytest


@pytest.fixture
def master(request, salt_factories):
    return salt_factories.spawn_master(request, 'master-1')


@pytest.fixture
def minion(request, salt_factories, master):
    return salt_factories.spawn_minion(request, 'minion-1', master_id='master-1')


@pytest.fixture
def salt_cli(request, salt_factories, minion, master):
    return salt_factories.get_salt_cli(request, master.config['id'])


def test_minion(minion, salt_cli):
    assert minion.is_alive()
    ret = salt_cli.run('test.ping', minion_tgt='minion-1')
    assert ret.exitcode == 0, ret
    assert ret.json is True
