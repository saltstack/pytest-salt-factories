import sys

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform.lower().startswith("win"),
    reason="Disabled on windows because of multiprocessing pickle spawning issues",
)


@pytest.fixture(scope="module")
def master(salt_factories):
    factory = salt_factories.get_salt_master_daemon("master-1")
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def proxy_minion(master):
    factory = master.get_salt_proxy_minion_daemon("proxy-minion-1")
    with factory.started():
        yield factory


@pytest.fixture
def salt_cli(master):
    return master.get_salt_cli()


@pytest.fixture
def salt_call_cli(proxy_minion):
    return proxy_minion.get_salt_call_cli()


def test_proxy_minion(proxy_minion, salt_cli):
    assert proxy_minion.is_running()
    ret = salt_cli.run("test.ping", minion_tgt="proxy-minion-1")
    assert ret.exitcode == 0, ret
    assert ret.json is True


def test_no_match(proxy_minion, salt_cli):
    assert proxy_minion.is_running()
    ret = salt_cli.run("test.ping", minion_tgt="proxy-minion-2")
    assert ret.exitcode == 2, ret
    assert not ret.json


def test_show_jid(proxy_minion, salt_cli):
    assert proxy_minion.is_running()
    ret = salt_cli.run("--show-jid", "test.ping", minion_tgt="proxy-minion-1")
    assert ret.exitcode == 0, ret
    assert ret.json is True


def test_proxy_minion_salt_call(proxy_minion, salt_call_cli):
    assert proxy_minion.is_running()
    ret = salt_call_cli.run("test.ping")
    assert ret.exitcode == 0, ret
    assert ret.json is True
    # Now with --local
    ret = salt_call_cli.run("--proxyid=proxy-minion-1", "test.ping")
    assert ret.exitcode == 0, ret
    assert ret.json is True
