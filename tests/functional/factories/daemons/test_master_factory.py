import pytest

from saltfactories.utils import random_string
from saltfactories.utils import running_username


def test_keyword_basic_defaults(salt_factories):
    master_config = salt_factories.salt_master_daemon(
        random_string("master-"), defaults={"zzzz": True}
    ).config
    assert "zzzz" in master_config


def test_interface_defaults(salt_factories):
    interface = "172.17.0.1"
    master_config = salt_factories.salt_master_daemon(
        random_string("master-"), defaults={"interface": interface}
    ).config
    assert master_config["interface"] != interface
    assert master_config["interface"] == "127.0.0.1"


def test_keyword_basic_overrides(salt_factories):
    master_config = salt_factories.salt_master_daemon(
        random_string("master-"), overrides={"zzzz": True}
    ).config
    assert "zzzz" in master_config


def test_interface_overrides(salt_factories):
    interface = "172.17.0.1"
    master_config = salt_factories.salt_master_daemon(
        random_string("master-"), overrides={"interface": interface}
    ).config
    assert master_config["interface"] != "127.0.0.1"
    assert master_config["interface"] == interface


def test_keyword_simple_overrides_override_defaults(salt_factories):
    master_config = salt_factories.salt_master_daemon(
        random_string("master-"), defaults={"zzzz": False}, overrides={"zzzz": True}
    ).config
    assert "zzzz" in master_config
    assert master_config["zzzz"] is True


def test_keyword_nested_overrides_override_defaults(salt_factories):
    master_config = salt_factories.salt_master_daemon(
        random_string("master-"),
        defaults={
            "zzzz": False,
            "user": "foobar",
            "colors": {"black": True, "white": False},
        },
        overrides={"colors": {"white": True, "grey": False}},
    ).config
    assert "zzzz" in master_config
    assert master_config["zzzz"] is False
    assert master_config["colors"] == {"black": True, "white": True, "grey": False}


def test_provide_root_dir(pytester, salt_factories):
    root_dir = str(pytester.mkdir("custom-root"))
    defaults = {"root_dir": root_dir}
    master_config = salt_factories.salt_master_daemon(
        random_string("master-"), defaults=defaults
    ).config
    assert master_config["root_dir"] == root_dir


def configure_kwargs_ids(value):
    return "configure_kwargs={!r}".format(value)


@pytest.mark.parametrize(
    "configure_kwargs",
    [{"defaults": {"user": "blah"}}, {"overrides": {"user": "blah"}}, {}],
    ids=configure_kwargs_ids,
)
def test_provide_user(salt_factories, configure_kwargs):
    master_config = salt_factories.salt_master_daemon(
        random_string("master-"), **configure_kwargs
    ).config
    if not configure_kwargs:
        # salt-factories injects the current username
        assert master_config["user"] is not None
        assert master_config["user"] == running_username()
    else:
        # salt-factories does not override the passed user value
        assert master_config["user"] != running_username()
        assert master_config["user"] == "blah"


@pytest.mark.parametrize(
    "configure_kwargs",
    [
        {"defaults": None},
        {"overrides": None},
        {},
        {"defaults": None, "overrides": {"user": "blah"}},
        {"defaults": {"user": "blah"}, "overrides": None},
        {"defaults": {"user": "blah"}, "overrides": {"user": "blah"}},
    ],
    ids=configure_kwargs_ids,
)
def test_pytest_config(salt_factories, configure_kwargs):
    master_id = random_string("master-")
    config = salt_factories.salt_master_daemon(master_id, **configure_kwargs).config
    config_key = "pytest-master"
    assert config_key in config
    assert "log" in config[config_key]
    for key in ("host", "level", "port", "prefix"):
        assert key in config[config_key]["log"]
