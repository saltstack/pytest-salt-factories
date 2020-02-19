# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import pytest


@pytest.fixture(scope="module")
def master_of_masters(request, salt_factories):
    """
    This is the master of all masters, top of the chain
    """
    return salt_factories.spawn_master(request, "master-of-masters", order_masters=True)


@pytest.fixture(scope="module")
def minion_1(request, salt_factories, master_of_masters):
    """
    This minion connects to the master-of-masters directly
    """
    assert master_of_masters.is_alive()
    return salt_factories.spawn_minion(request, "minion-1", master_id="master-of-masters")


@pytest.fixture(scope="module")
def configure_syndic(request, salt_factories, master_of_masters, minion_1):
    """
    This syndic will run in tandem with a master and minion which share the same ID, connected to the upstream
    master-of-masters master.
    """
    return salt_factories.configure_syndic(
        request, "syndic-1", master_of_masters_id=master_of_masters.config["id"],
    )


@pytest.fixture(scope="module")
def syndic_master(request, salt_factories, master_of_masters, configure_syndic):
    """
    This is a second master, which will connect to master-of-masters through the syndic.

    We depend on the minion_1 fixture just so we get both the master-of-masters and minion-1 fixtures running
    when this master starts.
    """
    return salt_factories.spawn_master(
        request, "syndic-1", master_of_masters_id=master_of_masters.config["id"],
    )


@pytest.fixture(scope="module")
def syndic_minion(request, salt_factories, syndic_master):
    """
    This is a second master, which will connect to master-of-masters through the syndic.

    We depend on the minion_1 fixture just so we get both the master-of-masters and minion-1 fixtures running
    when this master starts.
    """
    assert syndic_master.is_alive()
    return salt_factories.spawn_minion(request, "syndic-1", master_id=syndic_master.config["id"])


@pytest.fixture(scope="module")
def minion_2(request, salt_factories, syndic_master):
    """
    This minion will connect to the syndic-1 master
    """
    assert syndic_master.is_alive()
    return salt_factories.spawn_minion(request, "minion-2", master_id=syndic_master.config["id"])


@pytest.fixture(scope="module")
def master_of_masters_salt_cli(request, salt_factories, master_of_masters, minion_1):
    """
    This is the 'salt' CLI tool, connected to master-of-masters.
    Should be able to ping minion-1 directly connected to it and minion-2 through the syndic
    """
    assert master_of_masters.is_alive()
    assert minion_1.is_alive()
    return salt_factories.get_salt_cli(request, master_of_masters.config["id"])


@pytest.fixture(scope="module")
def syndic_master_salt_cli(request, salt_factories, syndic_master, syndic_minion, minion_2):
    """
    This is the 'salt' CLI tool, connected to master-of-masters.
    Should be able to ping minion-1 directly connected to it and minion-2 through the syndic
    """
    assert syndic_master.is_alive()
    assert syndic_minion.is_alive()
    assert minion_2.is_alive()
    return salt_factories.get_salt_cli(request, syndic_master.config["id"])


@pytest.fixture(scope="module")
def syndic(
    request, salt_factories, master_of_masters, minion_1, syndic_master, syndic_minion, minion_2
):
    """
    This syndic will run in tandem with master-2, connected to the upstream
    master-of-masters master.
    """
    assert master_of_masters.is_alive()
    assert minion_1.is_alive()
    assert syndic_master.is_alive()
    assert syndic_minion.is_alive()
    assert minion_2.is_alive()
    return salt_factories.spawn_syndic(
        request, syndic_master.config["id"], master_of_masters_id=master_of_masters.config["id"]
    )


@pytest.fixture(scope="module")
def salt_cli(master_of_masters_salt_cli, syndic_master_salt_cli, syndic):
    return master_of_masters_salt_cli


def test_minion_1(master_of_masters_salt_cli):
    """
    Just test that we can ping minion-1
    """
    ret = master_of_masters_salt_cli.run("test.ping", minion_tgt="minion-1", _timeout=60)
    assert ret.exitcode == 0, ret
    assert ret.json is True, ret


def test_minion_syndic_1(syndic_master_salt_cli):
    """
    Just test that we can ping minion-1
    """
    ret = syndic_master_salt_cli.run("test.ping", minion_tgt="syndic-1", _timeout=60)
    assert ret.exitcode == 0, ret
    assert ret.json is True, ret


def test_minion_2(syndic_master_salt_cli):
    """
    Just test that we can ping minion-2
    """
    ret = syndic_master_salt_cli.run("test.ping", minion_tgt="minion-2", _timeout=60)
    assert ret.exitcode == 0, ret
    assert ret.json is True, ret


@pytest.mark.skip("Syndics are still broken. Moving on for now")
def test_syndic(syndic, salt_cli):
    assert syndic.is_alive()
    # Are we able to ping the minion connected to the master-of-masters
    ret = salt_cli.run("test.ping", minion_tgt="minion-1", _timeout=60)
    assert ret.exitcode == 0, ret
    assert ret.json is True, ret
    # Are we able to ping the minions connected to the syndic-master
    ret = salt_cli.run("test.ping", minion_tgt="syndic-1", _timeout=60)
    assert ret.exitcode == 0, ret
    assert ret.json is True, ret
    ret = salt_cli.run("test.ping", minion_tgt="minion-2", _timeout=60)
    assert ret.exitcode == 0, ret
    assert ret.json is True, ret
    # Are we able to ping all of them?
    ret = salt_cli.run("test.ping", minion_tgt="*", _timeout=60)
    assert ret.exitcode == 0, ret
    assert "minion-1" in ret.json
    assert ret.json["minion-1"] is True
    assert "minion-2" in ret.json
    assert ret.json["minion-2"] is True
