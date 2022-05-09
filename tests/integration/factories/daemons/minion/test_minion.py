import pytest

from saltfactories.utils import random_string


@pytest.fixture(scope="module")
def master(salt_factories):
    factory = salt_factories.salt_master_daemon(random_string("master-"))
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def minion(master):
    factory = master.salt_minion_daemon(random_string("minion-"))
    with factory.started():
        yield factory


@pytest.fixture
def salt_cli(master):
    return master.salt_cli()


@pytest.fixture
def salt_call_cli(minion):
    return minion.salt_call_cli()


def test_minion(minion, salt_cli):
    assert minion.is_running()
    ret = salt_cli.run("test.ping", minion_tgt=minion.id)
    assert ret.returncode == 0, ret
    assert ret.data is True


def test_no_match(minion, salt_cli):
    assert minion.is_running()
    ret = salt_cli.run("test.ping", minion_tgt="minion-2")
    assert ret.returncode == 2, ret
    assert not ret.data


def test_show_jid(minion, salt_cli):
    assert minion.is_running()
    ret = salt_cli.run("--show-jid", "test.ping", minion_tgt=minion.id)
    assert ret.returncode == 0, ret
    assert ret.data is True


def test_minion_salt_call(minion, salt_call_cli):
    assert minion.is_running()
    ret = salt_call_cli.run("test.ping")
    assert ret.returncode == 0, ret
    assert ret.data is True
    # Now with --local
    ret = salt_call_cli.run("--local", "test.ping")
    assert ret.returncode == 0, ret
    assert ret.data is True


def test_salt_call_exception_handling_doesnt_timeout(minion, salt_call_cli):
    ret = salt_call_cli.run(
        "test.raise_exception", "OSError", "2", "No such file or directory", "/tmp/foo.txt"
    )
    assert ret.returncode == 1, ret


def test_state_tree(minion, salt_call_cli):
    sls_contents = """
    test:
      test.succeed_without_changes
    """
    with minion.state_tree.base.temp_file("foo.sls", sls_contents):
        ret = salt_call_cli.run("--local", "state.sls", "foo")
        assert ret.returncode == 0
