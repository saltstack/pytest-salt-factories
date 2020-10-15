import pytest

from saltfactories.utils import ports
from saltfactories.utils import random_string


@pytest.fixture(scope="module")
def master(salt_factories):
    config_defaults = {
        "rest_tornado": {"port": ports.get_unused_localhost_port(), "disable_ssl": True}
    }
    factory = salt_factories.get_salt_master_daemon(
        random_string("master-"), config_defaults=config_defaults
    )
    with factory.started():
        yield factory


def test_multiple_start_stops(master):
    factory = master.get_salt_api_daemon()
    assert factory.is_running() is False
    pid = None
    with factory.started():
        assert factory.is_running() is True
        pid = factory.pid
    assert factory.is_running() is False
    with factory.started():
        assert factory.is_running() is True
        assert factory.pid != pid
