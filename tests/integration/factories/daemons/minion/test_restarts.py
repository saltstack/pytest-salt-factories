import pytest

from saltfactories.utils import random_string


@pytest.fixture(scope="module")
def master(salt_factories):
    factory = salt_factories.get_salt_master_daemon(random_string("master-"))
    with factory.started():
        yield factory


def test_multiple_start_stops(master):
    factory = master.get_salt_minion_daemon(random_string("minion-"))
    assert factory.is_running() is False
    pid = None
    with factory.started():
        assert factory.is_running() is True
        pid = factory.pid
    assert factory.is_running() is False
    with factory.started():
        assert factory.is_running() is True
        assert factory.pid != pid
