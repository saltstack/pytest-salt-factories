# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import pytest


@pytest.fixture
def master_of_masters(request, salt_factories):
    return salt_factories.spawn_master(request, "master-of-masters")


@pytest.fixture
def syndic_master(request, salt_factories):
    return salt_factories.spawn_master(request, "syndic-master")


@pytest.fixture
def minion_1(request, salt_factories, master_of_masters):
    return salt_factories.spawn_minion(request, "minion-1", master_id="master-of-masters")


@pytest.fixture
def minion_2(request, salt_factories, syndic_master):
    return salt_factories.spawn_minion(request, "minion-2", master_id="syndic-master")


@pytest.fixture
def syndic(request, salt_factories, master_of_masters, syndic_master):
    return salt_factories.spawn_syndic(request, "syndic-1", master_id=syndic_master.config["id"])


@pytest.fixture
def salt_cli(request, salt_factories, master_of_masters):
    return salt_factories.get_salt_cli(request, master_of_masters.config["id"])


@pytest.mark.skip("Skipping for now")
def test_syndic(syndic, salt_cli):
    assert syndic.is_alive()
    # Are we able to ping the minion connected to the master-of-masters
    ret = salt_cli.run("test.ping", minion_tgt="minion-1")
    assert ret.exitcode == 0, ret
    assert ret.json is True, ret
    # Are we able to ping the minion connected to the syndic-master
    ret = salt_cli.run("test.ping", minion_tgt="minion-2")
    assert ret.exitcode == 0, ret
    assert ret.json is True, ret
    # Are we able to ping both?
    ret = salt_cli.run("test.ping", minion_tgt="*")
    assert ret.exitcode == 0, ret
    assert "minion-1" in ret.json
    assert ret.json["minion-1"] is True
    assert "minion-2" in ret.json
    assert ret.json["minion-2"] is True
