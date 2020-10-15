import pytest

from saltfactories.utils import random_string


@pytest.fixture(scope="module")
def master(salt_factories):
    factory = salt_factories.get_salt_master_daemon(random_string("master-"))
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def minion(master):
    factory = master.get_salt_minion_daemon(random_string("minion-"))
    with factory.started():
        yield factory


@pytest.fixture
def salt_cli(master):
    return master.get_salt_cli()


@pytest.fixture
def salt_call_cli(minion):
    return minion.get_salt_call_cli()


def test_minion(minion, salt_cli):
    assert minion.is_running()
    ret = salt_cli.run("test.ping", minion_tgt=minion.id)
    assert ret.exitcode == 0, ret
    assert ret.json is True


def test_no_match(minion, salt_cli):
    assert minion.is_running()
    ret = salt_cli.run("test.ping", minion_tgt="minion-2")
    assert ret.exitcode == 2, ret
    assert not ret.json


def test_show_jid(minion, salt_cli):
    assert minion.is_running()
    ret = salt_cli.run("--show-jid", "test.ping", minion_tgt=minion.id)
    assert ret.exitcode == 0, ret
    assert ret.json is True


def test_minion_salt_call(minion, salt_call_cli):
    assert minion.is_running()
    ret = salt_call_cli.run("test.ping")
    assert ret.exitcode == 0, ret
    assert ret.json is True
    # Now with --local
    ret = salt_call_cli.run("--local", "test.ping")
    assert ret.exitcode == 0, ret
    assert ret.json is True


def test_salt_call_exception_handling_doesnt_timeout(minion, salt_call_cli):
    ret = salt_call_cli.run(
        "test.raise_exception", "OSError", "2", "No such file or directory", "/tmp/foo.txt"
    )
    assert ret.exitcode == 1, ret
