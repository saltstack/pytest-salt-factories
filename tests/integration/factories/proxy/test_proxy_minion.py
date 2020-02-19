# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import sys

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform.lower().startswith("win"),
    reason="Disabled on windows because of multiprocessing pickle spawning issues",
)


@pytest.fixture(scope="module")
def master(request, salt_factories):
    return salt_factories.spawn_master(request, "master-1")


@pytest.fixture(scope="module")
def proxy_minion(request, salt_factories, master):
    return salt_factories.spawn_proxy_minion(request, "proxy-minion-1", master_id="master-1")


@pytest.fixture
def salt_cli(request, salt_factories, proxy_minion, master):
    return salt_factories.get_salt_cli(request, master.config["id"])


@pytest.fixture
def salt_call_cli(request, salt_factories, proxy_minion, master):
    return salt_factories.get_salt_call_cli(request, proxy_minion.config["id"])


def test_proxy_minion(proxy_minion, salt_cli):
    assert proxy_minion.is_alive()
    ret = salt_cli.run("test.ping", minion_tgt="proxy-minion-1")
    assert ret.exitcode == 0, ret
    assert ret.json is True


def test_no_match(proxy_minion, salt_cli):
    assert proxy_minion.is_alive()
    ret = salt_cli.run("test.ping", minion_tgt="proxy-minion-2")
    assert ret.exitcode == 2, ret
    assert not ret.json


def test_show_jid(proxy_minion, salt_cli):
    assert proxy_minion.is_alive()
    ret = salt_cli.run("--show-jid", "test.ping", minion_tgt="proxy-minion-1")
    assert ret.exitcode == 0, ret
    assert ret.json is True


def test_proxy_minion_salt_call(proxy_minion, salt_call_cli):
    assert proxy_minion.is_alive()
    ret = salt_call_cli.run("test.ping")
    assert ret.exitcode == 0, ret
    assert ret.json is True
    # Now with --local
    ret = salt_call_cli.run("--proxyid=proxy-minion-1", "test.ping")
    assert ret.exitcode == 0, ret
    assert ret.json is True
