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


@pytest.fixture(scope="module")
def salt_api(master):
    factory = master.get_salt_api_daemon()
    with factory.started():
        yield factory


def test_api(salt_api):
    assert salt_api.is_running()
