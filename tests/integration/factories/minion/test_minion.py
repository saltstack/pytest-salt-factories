# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import pytest


@pytest.fixture(scope="module")
def master(request, salt_factories):
    return salt_factories.spawn_master(request, "master-1")


@pytest.fixture(scope="module")
def minion(request, salt_factories, master):
    return salt_factories.spawn_minion(request, "minion-1", master_id="master-1")


@pytest.fixture
def salt_cli(request, salt_factories, minion, master):
    return salt_factories.get_salt_cli(request, master.config["id"])


@pytest.fixture
def salt_call_cli(request, salt_factories, minion, master):
    return salt_factories.get_salt_call_cli(request, minion.config["id"])


def test_minion(minion, salt_cli):
    assert minion.is_alive()
    ret = salt_cli.run("test.ping", minion_tgt="minion-1")
    assert ret.exitcode == 0, ret
    assert ret.json is True


def test_no_match(minion, salt_cli):
    assert minion.is_alive()
    ret = salt_cli.run("test.ping", minion_tgt="minion-2")
    assert ret.exitcode == 2, ret
    assert not ret.json


def test_show_jid(minion, salt_cli):
    assert minion.is_alive()
    ret = salt_cli.run("--show-jid", "test.ping", minion_tgt="minion-1")
    assert ret.exitcode == 0, ret
    assert ret.json is True


def test_minion_salt_call(minion, salt_call_cli):
    assert minion.is_alive()
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
