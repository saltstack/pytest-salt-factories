import logging

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


def test_logs_forwarded_from_sub_processes(salt_cli, minion, caplog):
    assert minion.is_running()

    with caplog.at_level(logging.DEBUG):
        ret = salt_cli.run("test.ping", minion_tgt=minion.id)
        assert ret.returncode == 0, ret
        assert ret.data is True

    non_main_processes_count = 0
    for record in caplog.records:
        if record.processName != "MainProcess":
            non_main_processes_count += 1

    # We should see at least a log record from the MWorker and ProcessPayload processes
    assert non_main_processes_count >= 2
