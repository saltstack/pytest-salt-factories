import pytest

from saltfactories.utils import random_string
from saltfactories.utils import running_username


def test_keyword_basic_defaults(salt_factories):
    proxy_minion_config = salt_factories.salt_proxy_minion_daemon(
        random_string("proxy-minion-"), defaults={"zzzz": True}
    ).config
    assert "zzzz" in proxy_minion_config


def test_keyword_basic_overrides(salt_factories):
    proxy_minion_config = salt_factories.salt_proxy_minion_daemon(
        random_string("proxy-minion-"), overrides={"zzzz": True}
    ).config
    assert "zzzz" in proxy_minion_config


def test_keyword_simple_overrides_override_defaults(salt_factories):
    proxy_minion_config = salt_factories.salt_proxy_minion_daemon(
        random_string("proxy-minion-"),
        defaults={"zzzz": False},
        overrides={"zzzz": True},
    ).config
    assert "zzzz" in proxy_minion_config
    assert proxy_minion_config["zzzz"] is True


def test_keyword_nested_overrides_override_defaults(salt_factories):
    proxy_minion_config = salt_factories.salt_proxy_minion_daemon(
        random_string("proxy-minion-"),
        defaults={
            "zzzz": False,
            "user": "foobar",
            "colors": {"black": True, "white": False},
        },
        overrides={"colors": {"white": True, "grey": False}},
    ).config
    assert "zzzz" in proxy_minion_config
    assert proxy_minion_config["zzzz"] is False
    assert proxy_minion_config["colors"] == {"black": True, "white": True, "grey": False}


def test_provide_root_dir(pytester, salt_factories):
    root_dir = str(pytester.mkdir("custom-root"))
    defaults = {"root_dir": root_dir}
    proxy_minion_config = salt_factories.salt_proxy_minion_daemon(
        random_string("proxy_minion-"), defaults=defaults
    ).config
    assert proxy_minion_config["root_dir"] == root_dir


def configure_kwargs_ids(value):
    return "configure_kwargs={!r}".format(value)


@pytest.mark.parametrize(
    "configure_kwargs",
    [{"defaults": {"user": "blah"}}, {"overrides": {"user": "blah"}}, {}],
    ids=configure_kwargs_ids,
)
def test_provide_user(salt_factories, configure_kwargs):
    proxy_minion_config = salt_factories.salt_proxy_minion_daemon(
        random_string("proxy-minion-"), **configure_kwargs
    ).config
    if not configure_kwargs:
        # salt-factories injects the current username
        assert proxy_minion_config["user"] is not None
        assert proxy_minion_config["user"] == running_username()
    else:
        # salt-factories does not override the passed user value
        assert proxy_minion_config["user"] != running_username()
        assert proxy_minion_config["user"] == "blah"


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
    master = salt_factories.salt_master_daemon(master_id)
    config = master.salt_proxy_minion_daemon(random_string("the-id-"), **configure_kwargs).config
    config_key = "pytest-minion"
    assert config_key in config
    assert "log" in config[config_key]
    for key in ("host", "level", "port", "prefix"):
        assert key in config[config_key]["log"]
    assert "master-id" in config[config_key]
    assert config[config_key]["master-id"] == master_id
