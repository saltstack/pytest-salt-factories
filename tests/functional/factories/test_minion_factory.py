# -*- coding: utf-8 -*-
"""
    tests.functional.factories.test_minion_factory
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Functional tests for the salt minion factory
"""
import pytest


def test_hook_basic_config_defaults(testdir):
    testdir.makeconftest(
        """
        def pytest_saltfactories_minion_configuration_defaults():
            return {'zzzz': True}
        """
    )
    p = testdir.makepyfile(
        """
        def test_basic_config_override(request, salt_factories):
            minion_config = salt_factories.configure_minion(request, 'minion-1')
            assert 'zzzz' in minion_config
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(passed=1)


def test_keyword_basic_config_defaults(request, salt_factories):
    minion_config = salt_factories.configure_minion(
        request, "minion-1", config_defaults={"zzzz": True}
    )
    assert "zzzz" in minion_config


def test_interface_config_defaults(request, salt_factories):
    interface = "172.17.0.1"
    master_config = salt_factories.configure_master(
        request, "master-1", config_defaults={"interface": interface}
    )
    assert master_config["interface"] != interface
    assert master_config["interface"] == "127.0.0.1"


def test_master_config_defaults(request, salt_factories):
    master = "172.17.0.1"
    minion_config = salt_factories.configure_minion(
        request, "minion-1", config_defaults={"master": master}
    )
    assert minion_config["master"] != master
    assert minion_config["master"] == "127.0.0.1"


def test_hook_basic_config_overrides(testdir):
    testdir.makeconftest(
        """
        def pytest_saltfactories_minion_configuration_overrides():
            return {'zzzz': True}
        """
    )
    p = testdir.makepyfile(
        """
        def test_basic_config_override(request, salt_factories):
            minion_config = salt_factories.configure_minion(request, 'minion-1')
            assert 'zzzz' in minion_config
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(passed=1)


def test_keyword_basic_config_overrides(request, salt_factories):
    minion_config = salt_factories.configure_minion(
        request, "minion-1", config_overrides={"zzzz": True}
    )
    assert "zzzz" in minion_config


def test_interface_config_overrides(request, salt_factories):
    interface = "172.17.0.1"
    master_config = salt_factories.configure_master(
        request, "master-1", config_overrides={"interface": interface}
    )
    assert master_config["interface"] == interface
    assert master_config["interface"] != "127.0.0.1"


def test_master_config_overrides(request, salt_factories):
    master = "172.17.0.1"
    minion_config = salt_factories.configure_minion(
        request, "minion-1", config_overrides={"master": master}
    )
    assert minion_config["master"] == master
    assert minion_config["master"] != "127.0.0.1"


def test_hook_simple_overrides_override_defaults(testdir):
    testdir.makeconftest(
        """
        def pytest_saltfactories_minion_configuration_defaults():
            return {'zzzz': False}

        def pytest_saltfactories_minion_configuration_overrides():
            return {'zzzz': True}
        """
    )
    p = testdir.makepyfile(
        """
        def test_basic_config_override(request, salt_factories):
            minion_config = salt_factories.configure_minion(request, 'minion-1')
            assert 'zzzz' in minion_config
            assert minion_config['zzzz'] is True
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(passed=1)


def test_keyword_simple_overrides_override_defaults(request, salt_factories):
    minion_config = salt_factories.configure_minion(
        request, "minion-1", config_defaults={"zzzz": False}, config_overrides={"zzzz": True}
    )
    assert "zzzz" in minion_config
    assert minion_config["zzzz"] is True


def test_hook_nested_overrides_override_defaults(testdir):
    testdir.makeconftest(
        """
        def pytest_saltfactories_minion_configuration_defaults():
            return {
                'zzzz': False,
                'user': 'foobar',
                'colors': {
                    'black': True,
                    'white': False
                }
            }

        def pytest_saltfactories_minion_configuration_overrides():
            return {
                'colors': {
                    'white': True,
                    'grey': False
                }
            }
        """
    )
    p = testdir.makepyfile(
        """
        def test_basic_config_override(request, salt_factories):
            minion_config = salt_factories.configure_minion(request, 'minion-1')
            assert 'zzzz' in minion_config
            assert minion_config['zzzz'] is False
            assert minion_config['colors'] == {
                'black': True,
                'white': True,
                'grey': False
            }
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(passed=1)


def test_keyword_nested_overrides_override_defaults(request, salt_factories):
    minion_config = salt_factories.configure_minion(
        request,
        "minion-1",
        config_defaults={
            "zzzz": False,
            "user": "foobar",
            "colors": {"black": True, "white": False},
        },
        config_overrides={"colors": {"white": True, "grey": False}},
    )
    assert "zzzz" in minion_config
    assert minion_config["zzzz"] is False
    assert minion_config["colors"] == {"black": True, "white": True, "grey": False}


def test_nested_overrides_override_defaults(testdir):
    testdir.makeconftest(
        """
        def pytest_saltfactories_minion_configuration_defaults():
            return {
                'zzzz': True,
                'user': 'foobar',
                'colors': {
                    'black': False,
                    'white': True,
                    'blue': False,
                }
            }

        def pytest_saltfactories_minion_configuration_overrides():
            return {
                'colors': {
                    'white': False,
                    'grey': True,
                    'blue': True,
                }
            }
        """
    )
    p = testdir.makepyfile(
        """
        def test_basic_config_override(request, salt_factories):
            minion_config = salt_factories.configure_minion(
                request,
                'minion-1',
                config_defaults={
                    'zzzz': False,
                    'user': 'foobar',
                    'colors': {
                        'black': True,
                        'white': False
                    }
                },
                config_overrides={
                    'colors': {
                        'white': True,
                        'grey': False
                    }
                }
            )
            assert 'zzzz' in minion_config
            assert minion_config['zzzz'] is False
            assert minion_config['colors'] == {
                'black': True,
                'white': True,
                'grey': False,
                'blue': True
            }
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(passed=1)


def test_provide_root_dir(testdir, request, salt_factories):
    root_dir = testdir.mkdir("custom-root")
    config_defaults = {"root_dir": root_dir}
    minion_config = salt_factories.configure_minion(
        request, "minion-1", config_defaults=config_defaults
    )
    assert minion_config["root_dir"] == root_dir


def configure_kwargs_ids(value):
    return "configure_kwargs={!r}".format(value)


@pytest.mark.parametrize(
    "configure_kwargs",
    [{"config_defaults": {"user": "blah"}}, {"config_overrides": {"user": "blah"}}, {}],
    ids=configure_kwargs_ids,
)
def test_provide_user(request, salt_factories, configure_kwargs):
    minion_config = salt_factories.configure_minion(request, "minion-1", **configure_kwargs)
    if not configure_kwargs:
        # salt-factories injects the current username
        assert minion_config["user"] is not None
        assert minion_config["user"] == salt_factories.get_running_username()
    else:
        # salt-factories does not override the passed user value
        assert minion_config["user"] != salt_factories.get_running_username()
        assert minion_config["user"] == "blah"
