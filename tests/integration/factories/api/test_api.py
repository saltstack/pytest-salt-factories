import pytest

from saltfactories.utils import ports


@pytest.fixture(scope="module")
def master(request, salt_factories):
    config_defaults = {
        "rest_tornado": {"port": ports.get_unused_localhost_port(), "disable_ssl": True}
    }
    return salt_factories.spawn_salt_master(request, "master-1", config_defaults=config_defaults)


@pytest.fixture(scope="module")
def salt_api(request, master):
    return master.spawn_salt_api(request)


def test_api(salt_api):
    assert salt_api.is_running()
