import pytest

from saltfactories.utils import random_string

pytestmark = [
    pytest.mark.skip_on_windows(
        reason="Disabled on windows because of multiprocessing pickle spawning issues",
    ),
]


@pytest.fixture(scope="module")
def master(salt_factories):
    factory = salt_factories.salt_master_daemon(random_string("master-"))
    with factory.started():
        yield factory


def test_multiple_start_stops(master):
    factory = master.salt_proxy_minion_daemon(random_string("proxy-minion-"))
    assert factory.is_running() is False
    pid = None
    with factory.started():
        assert factory.is_running() is True
        pid = factory.pid
    assert factory.is_running() is False
    with factory.started():
        assert factory.is_running() is True
        assert factory.pid != pid
