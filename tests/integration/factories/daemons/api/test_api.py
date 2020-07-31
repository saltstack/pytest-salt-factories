import pytest

from saltfactories.utils import ports


@pytest.fixture(scope="module")
def master(salt_factories):
    config_defaults = {
        "rest_tornado": {"port": ports.get_unused_localhost_port(), "disable_ssl": True}
    }
    factory = salt_factories.get_salt_master_daemon("master-1", config_defaults=config_defaults)
    factory.start()
    yield factory
    factory.terminate()


@pytest.fixture(scope="module")
def salt_api(master):
    factory = master.get_salt_api_daemon()
    factory.start()
    yield factory
    factory.terminate()


def test_api(salt_api):
    assert salt_api.is_running()
