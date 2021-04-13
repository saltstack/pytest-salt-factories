import pytest

from saltfactories.utils import random_string
from saltfactories.utils import running_username


@pytest.fixture
def mom(salt_factories):
    return salt_factories.salt_master_daemon(random_string("mom-"))


def test_keyword_basic_defaults(mom):
    syndic_id = random_string("syndic-")
    defaults = {"zzzz": True}
    master_defaults = defaults.copy()
    minion_defaults = defaults.copy()
    syndic = mom.salt_syndic_daemon(
        syndic_id,
        defaults=defaults,
        master_defaults=master_defaults,
        minion_defaults=minion_defaults,
    )
    assert "zzzz" in syndic.config
    assert syndic.config["zzzz"] is True
    assert "zzzz" in syndic.master.config
    assert syndic.master.config["zzzz"] is True
    assert "zzzz" in syndic.minion.config
    assert syndic.minion.config["zzzz"] is True


def test_keyword_basic_overrides(mom):
    syndic_id = random_string("syndic-")
    overrides = {"zzzz": True}
    master_overrides = overrides.copy()
    minion_overrides = overrides.copy()
    syndic = mom.salt_syndic_daemon(
        syndic_id,
        overrides=overrides,
        master_overrides=master_overrides,
        minion_overrides=minion_overrides,
    )
    assert "zzzz" in syndic.config
    assert syndic.config["zzzz"] is True
    assert "zzzz" in syndic.master.config
    assert syndic.master.config["zzzz"] is True
    assert "zzzz" in syndic.minion.config
    assert syndic.minion.config["zzzz"] is True


def test_keyword_simple_overrides_override_defaults(mom):
    syndic_id = random_string("syndic-")
    defaults = {"zzzz": False}
    master_defaults = defaults.copy()
    minion_defaults = defaults.copy()
    overrides = {"zzzz": True}
    master_overrides = overrides.copy()
    minion_overrides = overrides.copy()
    syndic = mom.salt_syndic_daemon(
        syndic_id,
        defaults=defaults,
        master_defaults=master_defaults,
        minion_defaults=minion_defaults,
        overrides=overrides,
        master_overrides=master_overrides,
        minion_overrides=minion_overrides,
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
    syndic = mom.salt_syndic_daemon(
        syndic_id,
        defaults=defaults,
        master_defaults=defaults.copy(),
        minion_defaults=defaults.copy(),
        overrides=overrides,
        master_overrides=overrides.copy(),
        minion_overrides=overrides.copy(),
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


def test_provide_root_dir(pytester, mom):
    root_dir = str(pytester.mkdir("custom-root"))
    defaults = {"root_dir": root_dir}
    syndic_id = random_string("syndic-")
    syndic = mom.salt_syndic_daemon(syndic_id, defaults=defaults)
    assert syndic.config["root_dir"] == root_dir


def configure_kwargs_ids(value):
    return "configure_kwargs={!r}".format(value)


@pytest.mark.parametrize(
    "configure_kwargs",
    [
        {
            "defaults": {"user": "blah"},
            "master_defaults": {"user": "blah"},
            "minion_defaults": {"user": "blah"},
        },
        {
            "overrides": {"user": "blah"},
            "master_overrides": {"user": "blah"},
            "minion_overrides": {"user": "blah"},
        },
        {},
    ],
    ids=configure_kwargs_ids,
)
def test_provide_user(salt_factories, mom, configure_kwargs):
    syndic_id = random_string("syndic-")
    syndic = mom.salt_syndic_daemon(syndic_id, **configure_kwargs)

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
