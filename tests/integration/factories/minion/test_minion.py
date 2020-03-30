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
def salt_cli(salt_factories, minion, master):
    return salt_factories.get_salt_cli(master.config["id"])


@pytest.fixture
def salt_call_cli(salt_factories, minion, master):
    return salt_factories.get_salt_call_cli(minion.config["id"])


@pytest.fixture
def salt_run_cli(salt_factories, minion, master):
    return salt_factories.get_salt_run_cli(master.config["id"])


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


@pytest.mark.skip_on_windows
def test_return(salt_call_cli, salt_run_cli):
    """
    This is a failing test on Salt's test suite
    """
    command = "echo returnTOmaster"
    ret = salt_call_cli.run("cmd.run", command)
    assert ret.exitcode == 0
    assert ret.json == "returnTOmaster"

    ret = salt_run_cli.run("jobs.list_jobs")
    assert ret.exitcode == 0
    jid = target = None
    for jid, details in ret.json.items():
        if command in details["Arguments"]:
            target = details["Target"]
            break

    ret = salt_run_cli.run("jobs.lookup_jid", jid, _timeout=60)
    assert ret.exitcode == 0
    assert target in ret.json
    assert ret.json[target] == "returnTOmaster"
