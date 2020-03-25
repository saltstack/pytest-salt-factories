# -*- coding: utf-8 -*-
"""
    tests.functional.factories.test_master_factory
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Functional tests for the salt master factory
"""
# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import pytest


def test_hook_basic_config_defaults(testdir):
    testdir.makeconftest(
        """
        def pytest_saltfactories_master_configuration_defaults():
            return {'zzzz': True}
        """
    )
    p = testdir.makepyfile(
        """
        def test_basic_config_override(request, salt_factories):
            master_config = salt_factories.configure_master(request, 'master-1')
            assert 'zzzz' in master_config
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(passed=1)


def test_keyword_basic_config_defaults(request, salt_factories):
    master_config = salt_factories.configure_master(
        request, "master-1", config_defaults={"zzzz": True}
    )
    assert "zzzz" in master_config


def test_hook_basic_config_overrides(testdir):
    testdir.makeconftest(
        """
        def pytest_saltfactories_master_configuration_overrides():
            return {'zzzz': True}
        """
    )
    p = testdir.makepyfile(
        """
        def test_basic_config_override(request, salt_factories):
            master_config = salt_factories.configure_master(request, 'master-1')
            assert 'zzzz' in master_config
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(passed=1)


def test_keyword_basic_config_overrides(request, salt_factories):
    master_config = salt_factories.configure_master(
        request, "master-1", config_overrides={"zzzz": True}
    )
    assert "zzzz" in master_config


def test_hook_simple_overrides_override_defaults(testdir):
    testdir.makeconftest(
        """
        def pytest_saltfactories_master_configuration_defaults():
            return {'zzzz': False}

        def pytest_saltfactories_master_configuration_overrides():
            return {'zzzz': True}
        """
    )
    p = testdir.makepyfile(
        """
        def test_basic_config_override(request, salt_factories):
            master_config = salt_factories.configure_master(request, 'master-1')
            assert 'zzzz' in master_config
            assert master_config['zzzz'] is True
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(passed=1)


def test_keyword_simple_overrides_override_defaults(request, salt_factories):
    master_config = salt_factories.configure_master(
        request, "master-1", config_defaults={"zzzz": False}, config_overrides={"zzzz": True}
    )
    assert "zzzz" in master_config
    assert master_config["zzzz"] is True


def test_hook_nested_overrides_override_defaults(testdir):
    testdir.makeconftest(
        """
        def pytest_saltfactories_master_configuration_defaults():
            return {
                'zzzz': False,
                'user': 'foobar',
                'colors': {
                    'black': True,
                    'white': False
                }
            }

        def pytest_saltfactories_master_configuration_overrides():
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
            master_config = salt_factories.configure_master(request, 'master-1')
            assert 'zzzz' in master_config
            assert master_config['zzzz'] is False
            assert master_config['colors'] == {
                'black': True,
                'white': True,
                'grey': False
            }
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(passed=1)


def test_keyword_nested_overrides_override_defaults(request, salt_factories):
    master_config = salt_factories.configure_master(
        request,
        "master-1",
        config_defaults={
            "zzzz": False,
            "user": "foobar",
            "colors": {"black": True, "white": False},
        },
        config_overrides={"colors": {"white": True, "grey": False}},
    )
    assert "zzzz" in master_config
    assert master_config["zzzz"] is False
    assert master_config["colors"] == {"black": True, "white": True, "grey": False}


def test_nested_overrides_override_defaults(testdir):
    testdir.makeconftest(
        """
        def pytest_saltfactories_master_configuration_defaults():
            return {
                'zzzz': True,
                'user': 'foobar',
                'colors': {
                    'black': False,
                    'white': True,
                    'blue': False
                }
            }

        def pytest_saltfactories_master_configuration_overrides():
            return {
                'colors': {
                    'white': False,
                    'grey': True,
                    'blue': True
                }
            }
        """
    )
    p = testdir.makepyfile(
        """
        def test_basic_config_override(request, salt_factories):
            master_config = salt_factories.configure_master(
                request,
                'master-1',
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
            assert 'zzzz' in master_config
            assert master_config['zzzz'] is False
            assert master_config['colors'] == {
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
    master_config = salt_factories.configure_master(
        request, "master-1", config_defaults=config_defaults
    )
    assert master_config["root_dir"] == root_dir


def configure_kwargs_ids(value):
    return "configure_kwargs={!r}".format(value)


@pytest.mark.parametrize(
    "configure_kwargs",
    [{"config_defaults": {"user": "blah"}}, {"config_overrides": {"user": "blah"}}, {}],
    ids=configure_kwargs_ids,
)
def test_provide_user(request, salt_factories, configure_kwargs):
    master_config = salt_factories.configure_master(request, "master-1", **configure_kwargs)
    if not configure_kwargs:
        # salt-factories injects the current username
        assert master_config["user"] is not None
        assert master_config["user"] == salt_factories.get_running_username()
    else:
        # salt-factories does not override the passed user value
        assert master_config["user"] != salt_factories.get_running_username()
        assert master_config["user"] == "blah"
