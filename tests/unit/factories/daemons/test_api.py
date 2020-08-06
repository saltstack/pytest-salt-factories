import pytest

from saltfactories.factories.daemons.api import SaltApiFactory
from saltfactories.utils import random_string


def test_missing_api_config(salt_factories):
    master = salt_factories.get_salt_master_daemon(random_string("master-"))
    with pytest.raises(RuntimeError) as exc:
        master.get_salt_api_daemon()

    assert str(exc.value) == (
        "The salt-master configuration for this salt-api instance does not seem to have "
        "any api properly configured."
    )


def test_configure_raises_exception(salt_factories):
    with pytest.raises(RuntimeError) as exc:
        SaltApiFactory.configure(salt_factories, "api")
    assert str(exc.value) == (
        "The salt-api daemon is not configurable. It uses the salt-master config that "
        "it's attached to."
    )


def test_load_config_raises_exception():
    with pytest.raises(RuntimeError) as exc:
        SaltApiFactory.load_config("config_file", {})
    assert str(exc.value) == (
        "The salt-api daemon does not have it's own config file. It uses the salt-master config that "
        "it's attached to."
    )
