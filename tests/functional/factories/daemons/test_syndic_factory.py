import re

import pytest

from saltfactories.utils import running_username


def test_keyword_basic_config_defaults_top_level_keys(salt_factories):
    with pytest.raises(RuntimeError) as exc:
        mom_config = salt_factories.get_salt_master_daemon("mom-1").config
        syndic_id = "syndic-1"
        syndic_config = salt_factories.get_salt_syndic_daemon(
            syndic_id, master_of_masters_id="mom-1", config_defaults={"zzzz": True}
        ).config

    assert (
        re.match(
            r"The config_defaults keyword argument must only contain 3 top level keys: .*",
            str(exc.value),
        )
        is not None
    )


def test_keyword_basic_config_overrides_top_level_keys(salt_factories):
    with pytest.raises(RuntimeError) as exc:
        mom_config = salt_factories.get_salt_master_daemon("mom-1").config
        syndic_id = "syndic-1"
        syndic_config = salt_factories.get_salt_syndic_daemon(
            syndic_id, master_of_masters_id="mom-1", config_overrides={"zzzz": True}
        ).config

    assert re.match(
        r"The config_overrides keyword argument must only contain 3 top level keys: .*",
        str(exc.value),
    )


def test_keyword_basic_config_defaults(salt_factories):
    mom_config = salt_factories.get_salt_master_daemon("mom-1").config
    syndic_id = "syndic-1"
    config_defaults = {
        "syndic": {"zzzz": True},
        "master": {"zzzz": True},
        "minion": {"zzzz": True},
    }
    syndic_config = salt_factories.get_salt_syndic_daemon(
        syndic_id, master_of_masters_id="mom-1", config_defaults=config_defaults
    ).config
    assert "zzzz" in syndic_config
    assert syndic_config["zzzz"] is True
    syndic_master_config = salt_factories.get_salt_master_daemon(syndic_id).config
    assert "zzzz" in syndic_master_config
    assert syndic_master_config["zzzz"] is True
    syndic_minion_config = salt_factories.get_salt_minion_daemon(syndic_id).config
    assert "zzzz" in syndic_minion_config
    assert syndic_minion_config["zzzz"] is True


def test_keyword_basic_config_overrides(salt_factories):
    mom_config = salt_factories.get_salt_master_daemon("mom-1").config
    syndic_id = "syndic-1"
    config_overrides = {
        "syndic": {"zzzz": True},
        "master": {"zzzz": True},
        "minion": {"zzzz": True},
    }
    syndic_config = salt_factories.get_salt_syndic_daemon(
        syndic_id, master_of_masters_id="mom-1", config_overrides=config_overrides
    ).config
    assert "zzzz" in syndic_config
    assert syndic_config["zzzz"] is True
    syndic_master_config = salt_factories.get_salt_master_daemon(syndic_id).config
    assert "zzzz" in syndic_master_config
    assert syndic_master_config["zzzz"] is True
    syndic_minion_config = salt_factories.get_salt_minion_daemon(syndic_id).config
    assert "zzzz" in syndic_minion_config
    assert syndic_minion_config["zzzz"] is True


def test_keyword_simple_overrides_override_defaults(salt_factories):
    mom_config = salt_factories.get_salt_master_daemon("mom-1").config
    syndic_id = "syndic-1"
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
    syndic_config = salt_factories.get_salt_syndic_daemon(
        syndic_id,
        master_of_masters_id="mom-1",
        config_defaults=config_defaults,
        config_overrides=config_overrides,
    ).config
    assert "zzzz" in syndic_config
    assert syndic_config["zzzz"] is True
    syndic_master_config = salt_factories.get_salt_master_daemon(syndic_id).config
    assert "zzzz" in syndic_master_config
    assert syndic_master_config["zzzz"] is True
    syndic_minion_config = salt_factories.get_salt_minion_daemon(syndic_id).config
    assert "zzzz" in syndic_minion_config
    assert syndic_minion_config["zzzz"] is True


def test_keyword_nested_overrides_override_defaults(salt_factories):
    defaults = {"zzzz": False, "user": "foobar", "colors": {"black": True, "white": False}}
    overrides = {"zzzz": True, "colors": {"white": True, "grey": False}}
    expected_colors = {"black": True, "white": True, "grey": False}
    mom_config = salt_factories.get_salt_master_daemon("mom-1").config
    syndic_id = "syndic-1"
    syndic_config = salt_factories.get_salt_syndic_daemon(
        syndic_id,
        master_of_masters_id="mom-1",
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
    ).config
    assert "zzzz" in syndic_config
    assert syndic_config["zzzz"] is True
    assert syndic_config["colors"] == expected_colors
    syndic_master_config = salt_factories.get_salt_master_daemon(syndic_id).config
    assert "zzzz" in syndic_master_config
    assert syndic_master_config["zzzz"] is True
    assert syndic_master_config["colors"] == expected_colors
    syndic_minion_config = salt_factories.get_salt_minion_daemon(syndic_id).config
    assert "zzzz" in syndic_minion_config
    assert syndic_minion_config["zzzz"] is True
    assert syndic_minion_config["colors"] == expected_colors


def test_provide_root_dir(testdir, salt_factories):
    mom_config = salt_factories.get_salt_master_daemon("mom-1").config
    root_dir = testdir.mkdir("custom-root")
    config_defaults = {
        "syndic": {"root_dir": root_dir},
    }
    syndic_id = "syndic-1"
    syndic_config = salt_factories.get_salt_syndic_daemon(
        syndic_id, master_of_masters_id="mom-1", config_defaults=config_defaults
    ).config
    syndic_config = salt_factories.get_salt_syndic_daemon(
        "syndic-1", config_defaults=config_defaults
    ).config
    assert syndic_config["root_dir"] == root_dir


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
def test_provide_user(salt_factories, configure_kwargs):
    mom_config = salt_factories.get_salt_master_daemon("mom-1").config
    configure_salt_syndic_kwargs = configure_kwargs.copy()
    configure_salt_syndic_kwargs["master_of_masters_id"] = "mom-1"

    syndic_id = "syndic-1"
    syndic_config = salt_factories.get_salt_syndic_daemon(
        syndic_id, **configure_salt_syndic_kwargs
    ).config

    if not configure_kwargs:
        # salt-factories injects the current username
        master_config = salt_factories.cache["masters"][syndic_id].config
        assert master_config["user"] is not None
        assert master_config["user"] == running_username()
        minion_config = salt_factories.cache["minions"][syndic_id].config
        assert minion_config["user"] is not None
        assert minion_config["user"] == running_username()
        assert syndic_config["user"] is not None
        assert syndic_config["user"] == running_username()
    else:
        master_config = salt_factories.cache["masters"][syndic_id].config
        assert master_config["user"] != running_username()
        assert master_config["user"] == "blah"
        minion_config = salt_factories.cache["minions"][syndic_id].config
        assert minion_config["user"] != running_username()
        assert minion_config["user"] == "blah"
        # salt-factories does not override the passed user value
        assert syndic_config["user"] != running_username()
        assert syndic_config["user"] == "blah"
