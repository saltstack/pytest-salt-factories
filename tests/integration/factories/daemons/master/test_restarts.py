import pytest

from saltfactories.utils import random_string


@pytest.fixture(scope="module")
def master(salt_factories):
    factory = salt_factories.get_salt_master_daemon(
        random_string("master-"), config_overrides={"max_open_files": 4096}
    )
    return factory


def test_multiple_start_stops(master):
    assert master.is_running() is False
    pid = None
    with master.started():
        assert master.is_running() is True
        pid = master.pid
    assert master.is_running() is False
    with master.started():
        assert master.is_running() is True
        assert master.pid != pid
