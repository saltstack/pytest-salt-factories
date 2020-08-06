import re

import pytest

from saltfactories.utils import random_string
from saltfactories.utils import running_username


@pytest.fixture
def mom(salt_factories):
    return salt_factories.get_salt_master_daemon(random_string("mom-"))


def test_keyword_basic_config_defaults_top_level_keys(mom):
    with pytest.raises(RuntimeError) as exc:
        syndic_id = random_string("syndic-")
        syndic = mom.get_salt_syndic_daemon(syndic_id, config_defaults={"zzzz": True})

    assert (
        re.match(
            r"The config_defaults keyword argument must only contain 3 top level keys: .*",
            str(exc.value),
        )
        is not None
    )


def test_keyword_basic_config_overrides_top_level_keys(mom):
    with pytest.raises(RuntimeError) as exc:
        syndic_id = random_string("syndic-")
        syndic_config = mom.get_salt_syndic_daemon(syndic_id, config_overrides={"zzzz": True})

    assert re.match(
        r"The config_overrides keyword argument must only contain 3 top level keys: .*",
        str(exc.value),
    )


def test_keyword_basic_config_defaults(mom):
    syndic_id = random_string("syndic-")
    config_defaults = {
        "syndic": {"zzzz": True},
        "master": {"zzzz": True},
        "minion": {"zzzz": True},
    }
    syndic = mom.get_salt_syndic_daemon(syndic_id, config_defaults=config_defaults)
    assert "zzzz" in syndic.config
    assert syndic.config["zzzz"] is True
    syndic_master = mom.get_salt_master_daemon(syndic_id)
    assert "zzzz" in syndic_master.config
    assert syndic_master.config["zzzz"] is True
    syndic_minion = mom.get_salt_minion_daemon(syndic_id)
    assert "zzzz" in syndic_minion.config
    assert syndic_minion.config["zzzz"] is True


def test_keyword_basic_config_overrides(mom):
    syndic_id = random_string("syndic-")
    config_overrides = {
        "syndic": {"zzzz": True},
        "master": {"zzzz": True},
        "minion": {"zzzz": True},
    }
    syndic = mom.get_salt_syndic_daemon(syndic_id, config_overrides=config_overrides)
    assert "zzzz" in syndic.config
    assert syndic.config["zzzz"] is True
    syndic_master = mom.get_salt_master_daemon(syndic_id)
    assert "zzzz" in syndic_master.config
    assert syndic_master.config["zzzz"] is True
    syndic_minion = mom.get_salt_minion_daemon(syndic_id)
    assert "zzzz" in syndic_minion.config
    assert syndic_minion.config["zzzz"] is True


def test_keyword_simple_overrides_override_defaults(mom):
    syndic_id = random_string("syndic-")
    config_defaults = {
        "syndic": {"zzzz": False},
        "master": {"zzzz": False},
        "minion": {"zzzz": False},
    }
    config_overrides = {
        "syndic": {"zzzz": True},
        "master": {"zzzz": True},
        "minion": {"zzzz": True},
    }
    syndic = mom.get_salt_syndic_daemon(
        syndic_id, config_defaults=config_defaults, config_overrides=config_overrides,
    )
    assert "zzzz" in syndic.config
    assert syndic.config["zzzz"] is True
    syndic_master = mom.get_salt_master_daemon(syndic_id)
    assert "zzzz" in syndic_master.config
    assert syndic_master.config["zzzz"] is True
    syndic_minion = mom.get_salt_minion_daemon(syndic_id)
    assert "zzzz" in syndic_minion.config
    assert syndic_minion.config["zzzz"] is True


def test_keyword_nested_overrides_override_defaults(mom):
    defaults = {"zzzz": False, "user": "foobar", "colors": {"black": True, "white": False}}
    overrides = {"zzzz": True, "colors": {"white": True, "grey": False}}
    expected_colors = {"black": True, "white": True, "grey": False}
    syndic_id = random_string("syndic-")
    syndic = mom.get_salt_syndic_daemon(
        syndic_id,
        config_defaults={
            "syndic": defaults.copy(),
            "master": defaults.copy(),
            "minion": defaults.copy(),
        },
        config_overrides={
            "syndic": overrides.copy(),
            "master": overrides.copy(),
            "minion": overrides.copy(),
        },
    )
    assert "zzzz" in syndic.config
    assert syndic.config["zzzz"] is True
    assert syndic.config["colors"] == expected_colors
    syndic_master = mom.get_salt_master_daemon(syndic_id)
    assert "zzzz" in syndic_master.config
    assert syndic_master.config["zzzz"] is True
    assert syndic_master.config["colors"] == expected_colors
    syndic_minion = mom.get_salt_minion_daemon(syndic_id)
    assert "zzzz" in syndic_minion.config
    assert syndic_minion.config["zzzz"] is True
    assert syndic_minion.config["colors"] == expected_colors


def test_provide_root_dir(testdir, mom):
    root_dir = testdir.mkdir("custom-root")
    config_defaults = {
        "syndic": {"root_dir": root_dir},
    }
    syndic_id = random_string("syndic-")
    syndic = mom.get_salt_syndic_daemon(syndic_id, config_defaults=config_defaults)
    assert syndic.config["root_dir"] == root_dir


def configure_kwargs_ids(value):
    return "configure_kwargs={!r}".format(value)


@pytest.mark.parametrize(
    "configure_kwargs",
    [
        {
            "config_defaults": {
                "syndic": {"user": "blah"},
                "minion": {"user": "blah"},
                "master": {"user": "blah"},
            }
        },
        {
            "config_overrides": {
                "syndic": {"user": "blah"},
                "minion": {"user": "blah"},
                "master": {"user": "blah"},
            }
        },
        {},
    ],
    ids=configure_kwargs_ids,
)
def test_provide_user(salt_factories, mom, configure_kwargs):
    syndic_id = random_string("syndic-")
    syndic = mom.get_salt_syndic_daemon(syndic_id, **configure_kwargs)

    if not configure_kwargs:
        # salt-factories injects the current username
        master = salt_factories.cache["masters"][syndic_id]
        assert master.config["user"] is not None
        assert master.config["user"] == running_username()
        minion = salt_factories.cache["minions"][syndic_id]
        assert minion.config["user"] is not None
        assert minion.config["user"] == running_username()
        assert syndic.config["user"] is not None
        assert syndic.config["user"] == running_username()
    else:
        master = salt_factories.cache["masters"][syndic_id]
        assert master.config["user"] != running_username()
        assert master.config["user"] == "blah"
        minion = salt_factories.cache["minions"][syndic_id]
        assert minion.config["user"] != running_username()
        assert minion.config["user"] == "blah"
        # salt-factories does not override the passed user value
        assert syndic.config["user"] != running_username()
        assert syndic.config["user"] == "blah"
