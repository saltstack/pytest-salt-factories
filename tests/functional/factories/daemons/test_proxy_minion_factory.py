import pytest

from saltfactories.utils import running_username


def test_keyword_basic_config_defaults(salt_factories):
    proxy_minion_config = salt_factories.get_salt_proxy_minion_daemon(
        "proxy-minion-1", config_defaults={"zzzz": True}
    ).config
    assert "zzzz" in proxy_minion_config


def test_keyword_basic_config_overrides(salt_factories):
    proxy_minion_config = salt_factories.get_salt_proxy_minion_daemon(
        "proxy-minion-1", config_overrides={"zzzz": True}
    ).config
    assert "zzzz" in proxy_minion_config


def test_keyword_simple_overrides_override_defaults(salt_factories):
    proxy_minion_config = salt_factories.get_salt_proxy_minion_daemon(
        "proxy-minion-1", config_defaults={"zzzz": False}, config_overrides={"zzzz": True}
    ).config
    assert "zzzz" in proxy_minion_config
    assert proxy_minion_config["zzzz"] is True


def test_keyword_nested_overrides_override_defaults(salt_factories):
    proxy_minion_config = salt_factories.get_salt_proxy_minion_daemon(
        "proxy-minion-1",
        config_defaults={
            "zzzz": False,
            "user": "foobar",
            "colors": {"black": True, "white": False},
        },
        config_overrides={"colors": {"white": True, "grey": False}},
    ).config
    assert "zzzz" in proxy_minion_config
    assert proxy_minion_config["zzzz"] is False
    assert proxy_minion_config["colors"] == {"black": True, "white": True, "grey": False}


def test_provide_root_dir(testdir, salt_factories):
    root_dir = testdir.mkdir("custom-root")
    config_defaults = {"root_dir": root_dir}
    proxy_minion_config = salt_factories.get_salt_proxy_minion_daemon(
        "proxy_minion-1", config_defaults=config_defaults
    ).config
    assert proxy_minion_config["root_dir"] == root_dir


def configure_kwargs_ids(value):
    return "configure_kwargs={!r}".format(value)


@pytest.mark.parametrize(
    "configure_kwargs",
    [{"config_defaults": {"user": "blah"}}, {"config_overrides": {"user": "blah"}}, {}],
    ids=configure_kwargs_ids,
)
def test_provide_user(salt_factories, configure_kwargs):
    proxy_minion_config = salt_factories.get_salt_proxy_minion_daemon(
        "proxy-minion-1", **configure_kwargs
    ).config
    if not configure_kwargs:
        # salt-factories injects the current username
        assert proxy_minion_config["user"] is not None
        assert proxy_minion_config["user"] == running_username()
    else:
        # salt-factories does not override the passed user value
        assert proxy_minion_config["user"] != running_username()
        assert proxy_minion_config["user"] == "blah"
