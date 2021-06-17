import sys

import pytest

from saltfactories.utils import platform
from saltfactories.utils import random_string

pytestmark = pytest.mark.skipif(
    sys.platform.lower().startswith("win"),
    reason="Disabled on windows because of multiprocessing pickle spawning issues",
)


@pytest.fixture(scope="module")
def master(salt_factories):
    factory = salt_factories.salt_master_daemon(random_string("master-"))
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def proxy_minion(master):
    factory = master.salt_proxy_minion_daemon(random_string("proxy-minion-"))
    with factory.started():
        yield factory


@pytest.fixture
def salt_cli(master):
    return master.salt_cli()


@pytest.fixture
def salt_call_cli(proxy_minion):
    return proxy_minion.salt_call_cli()


def test_proxy_minion(proxy_minion, salt_cli):
    assert proxy_minion.is_running()
    ret = salt_cli.run("test.ping", minion_tgt=proxy_minion.id)
    assert ret.exitcode == 0, ret
    assert ret.json is True


def test_no_match(proxy_minion, salt_cli):
    assert proxy_minion.is_running()
    ret = salt_cli.run("test.ping", minion_tgt="proxy-minion-2")
    assert ret.exitcode == 2, ret
    assert not ret.json


def test_show_jid(proxy_minion, salt_cli):
    if platform.is_darwin() and sys.version_info[:2] == (3, 7):
        pytest.skip(
            "This test passes on Darwin under Py3.7, it has the expected output "
            "and yet, it times out. Will investigate later."
        )
    assert proxy_minion.is_running()
    ret = salt_cli.run("--show-jid", "test.ping", minion_tgt=proxy_minion.id)
    assert ret.exitcode == 0, ret
    assert ret.json is True


def test_proxy_minion_salt_call(proxy_minion, salt_call_cli):
    assert proxy_minion.is_running()
    ret = salt_call_cli.run("test.ping")
    assert ret.exitcode == 0, ret
    assert ret.json is True
    # Now with --local
    ret = salt_call_cli.run("--proxyid={}".format(proxy_minion.id), "test.ping")
    assert ret.exitcode == 0, ret
    assert ret.json is True


def test_state_tree(proxy_minion, salt_call_cli):
    sls_contents = """
    test:
      test.succeed_without_changes
    """
    with proxy_minion.state_tree.base.temp_file("foo.sls", sls_contents):
        ret = salt_call_cli.run("--local", "state.sls", "foo")
        assert ret.exitcode == 0
