import pytest

pytestmark = pytest.mark.skip(reason="Skipping until we devote time to fix syndic support")


@pytest.fixture(scope="module")
def master_of_masters(salt_factories):
    """
    This is the master of all masters, top of the chain
    """
    factory = salt_factories.get_salt_master_daemon("master-of-masters", order_masters=True)
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def minion_1(master_of_masters):
    """
    This minion connects to the master-of-masters directly
    """
    assert master_of_masters.is_running()
    factory = master_of_masters.get_salt_minion_daemon("minion-1")
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def configure_salt_syndic(master_of_masters, minion_1):
    """
    This syndic will run in tandem with a master and minion which share the same ID, connected to the upstream
    master-of-masters master.
    """
    factory = master_of_masters.get_salt_syndic_daemon("syndic-1")
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def syndic_master(master_of_masters, configure_salt_syndic):
    """
    This is a second master, which will connect to master-of-masters through the syndic.

    We depend on the minion_1 fixture just so we get both the master-of-masters and minion-1 fixtures running
    when this master starts.
    """
    factory = master_of_masters.get_salt_master_daemon("syndic-1")
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def syndic_minion(syndic_master):
    """
    This is a second master, which will connect to master-of-masters through the syndic.

    We depend on the minion_1 fixture just so we get both the master-of-masters and minion-1 fixtures running
    when this master starts.
    """
    assert syndic_master.is_running()
    factory = syndic_master.get_salt_minion_daemon("syndic-1")
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def minion_2(syndic_master):
    """
    This minion will connect to the syndic-1 master
    """
    assert syndic_master.is_running()
    factory = syndic_master.get_salt_minion_daemon("minion-2")
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def master_of_masters_salt_cli(master_of_masters, minion_1):
    """
    This is the 'salt' CLI tool, connected to master-of-masters.
    Should be able to ping minion-1 directly connected to it and minion-2 through the syndic
    """
    assert master_of_masters.is_running()
    assert minion_1.is_running()
    return master_of_masters.get_salt_cli()


@pytest.fixture(scope="module")
def syndic_master_salt_cli(syndic_master, syndic_minion, minion_2):
    """
    This is the 'salt' CLI tool, connected to master-of-masters.
    Should be able to ping minion-1 directly connected to it and minion-2 through the syndic
    """
    assert syndic_master.is_running()
    assert syndic_minion.is_running()
    assert minion_2.is_running()
    return syndic_master.get_salt_cli()


@pytest.fixture(scope="module")
def syndic(salt_factories, master_of_masters, minion_1, syndic_master, syndic_minion, minion_2):
    """
    This syndic will run in tandem with master-2, connected to the upstream
    master-of-masters master.
    """
    assert master_of_masters.is_running()
    assert minion_1.is_running()
    assert syndic_master.is_running()
    assert syndic_minion.is_running()
    assert minion_2.is_running()
    return master_of_masters.get_salt_syndic_daemon(syndic_master.id)


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
    assert syndic.is_running()
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
