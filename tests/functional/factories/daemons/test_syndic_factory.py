import pytest

from saltfactories.utils import random_string
from saltfactories.utils import running_username


@pytest.fixture
def mom(salt_factories):
    return salt_factories.get_salt_master_daemon(random_string("mom-"))


def test_keyword_basic_config_defaults(mom):
    syndic_id = random_string("syndic-")
    config_defaults = {"zzzz": True}
    master_config_defaults = config_defaults.copy()
    minion_config_defaults = config_defaults.copy()
    syndic = mom.get_salt_syndic_daemon(
        syndic_id,
        config_defaults=config_defaults,
        master_config_defaults=master_config_defaults,
        minion_config_defaults=minion_config_defaults,
    )
    assert "zzzz" in syndic.config
    assert syndic.config["zzzz"] is True
    assert "zzzz" in syndic.master.config
    assert syndic.master.config["zzzz"] is True
    assert "zzzz" in syndic.minion.config
    assert syndic.minion.config["zzzz"] is True


def test_keyword_basic_config_overrides(mom):
    syndic_id = random_string("syndic-")
    config_overrides = {"zzzz": True}
    master_config_overrides = config_overrides.copy()
    minion_config_overrides = config_overrides.copy()
    syndic = mom.get_salt_syndic_daemon(
        syndic_id,
        config_overrides=config_overrides,
        master_config_overrides=master_config_overrides,
        minion_config_overrides=minion_config_overrides,
    )
    assert "zzzz" in syndic.config
    assert syndic.config["zzzz"] is True
    assert "zzzz" in syndic.master.config
    assert syndic.master.config["zzzz"] is True
    assert "zzzz" in syndic.minion.config
    assert syndic.minion.config["zzzz"] is True


def test_keyword_simple_overrides_override_defaults(mom):
    syndic_id = random_string("syndic-")
    config_defaults = {"zzzz": False}
    master_config_defaults = config_defaults.copy()
    minion_config_defaults = config_defaults.copy()
    config_overrides = {"zzzz": True}
    master_config_overrides = config_overrides.copy()
    minion_config_overrides = config_overrides.copy()
    syndic = mom.get_salt_syndic_daemon(
        syndic_id,
        config_defaults=config_defaults,
        master_config_defaults=master_config_defaults,
        minion_config_defaults=minion_config_defaults,
        config_overrides=config_overrides,
        master_config_overrides=master_config_overrides,
        minion_config_overrides=minion_config_overrides,
    )
    assert "zzzz" in syndic.config
    assert syndic.config["zzzz"] is True
    assert "zzzz" in syndic.master.config
    assert syndic.master.config["zzzz"] is True
    assert "zzzz" in syndic.minion.config
    assert syndic.minion.config["zzzz"] is True


def test_keyword_nested_overrides_override_defaults(mom):
    defaults = {"zzzz": False, "user": "foobar", "colors": {"black": True, "white": False}}
    overrides = {"zzzz": True, "colors": {"white": True, "grey": False}}
    expected_colors = {"black": True, "white": True, "grey": False}
    syndic_id = random_string("syndic-")
    syndic = mom.get_salt_syndic_daemon(
        syndic_id,
        config_defaults=defaults,
        master_config_defaults=defaults.copy(),
        minion_config_defaults=defaults.copy(),
        config_overrides=overrides,
        master_config_overrides=overrides.copy(),
        minion_config_overrides=overrides.copy(),
    )
    assert "zzzz" in syndic.config
    assert syndic.config["zzzz"] is True
    assert syndic.config["colors"] == expected_colors
    assert "zzzz" in syndic.master.config
    assert syndic.master.config["zzzz"] is True
    assert syndic.master.config["colors"] == expected_colors
    assert "zzzz" in syndic.minion.config
    assert syndic.minion.config["zzzz"] is True
    assert syndic.minion.config["colors"] == expected_colors


def test_provide_root_dir(testdir, mom):
    root_dir = testdir.mkdir("custom-root")
    config_defaults = {"root_dir": root_dir}
    syndic_id = random_string("syndic-")
    syndic = mom.get_salt_syndic_daemon(syndic_id, config_defaults=config_defaults)
    assert syndic.config["root_dir"] == root_dir


def configure_kwargs_ids(value):
    return "configure_kwargs={!r}".format(value)


@pytest.mark.parametrize(
    "configure_kwargs",
    [
        {
            "config_defaults": {"user": "blah"},
            "master_config_defaults": {"user": "blah"},
            "minion_config_defaults": {"user": "blah"},
        },
        {
            "config_overrides": {"user": "blah"},
            "master_config_overrides": {"user": "blah"},
            "minion_config_overrides": {"user": "blah"},
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
        assert syndic.master.config["user"] is not None
        assert syndic.master.config["user"] == running_username()
        assert syndic.minion.config["user"] is not None
        assert syndic.minion.config["user"] == running_username()
        assert syndic.config["user"] is not None
        assert syndic.config["user"] == running_username()
    else:
        assert syndic.master.config["user"] != running_username()
        assert syndic.master.config["user"] == "blah"
        assert syndic.minion.config["user"] != running_username()
        assert syndic.minion.config["user"] == "blah"
        # salt-factories does not override the passed user value
        assert syndic.config["user"] != running_username()
        assert syndic.config["user"] == "blah"
