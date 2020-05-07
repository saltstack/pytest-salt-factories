# -*- coding: utf-8 -*-
"""
    tests.functional.factories.test_syndic_factory
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Functional tests for the salt syndic factory
"""
import re

import pytest


def test_hook_basic_config_defaults_top_level_keys(testdir):
    testdir.makeconftest(
        """
        def pytest_saltfactories_syndic_configuration_defaults():
            return {
                'zzzz': True
            }
        """
    )
    p = testdir.makepyfile(
        """
        def test_basic_config_override(request, salt_factories):
            mom_config = salt_factories.configure_master(request, 'mom-1')
            syndic_id = 'syndic-1'
            syndic_config = salt_factories.configure_syndic(request, syndic_id, master_of_masters_id='mom-1')
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(failed=1)
    res.stdout.fnmatch_lines(
        ["*RuntimeError: The config defaults returned by * must only contain 3 top level keys: *"]
    )


def test_keyword_basic_config_defaults_top_level_keys(request, salt_factories):
    with pytest.raises(RuntimeError) as exc:
        mom_config = salt_factories.configure_master(request, "mom-1")
        syndic_id = "syndic-1"
        syndic_config = salt_factories.configure_syndic(
            request, syndic_id, master_of_masters_id="mom-1", config_defaults={"zzzz": True}
        )

    assert (
        re.match(
            r"The config_defaults keyword argument must only contain 3 top level keys: .*",
            str(exc.value),
        )
        is not None
    )


def test_hook_basic_config_overrides_top_level_keys(testdir):
    testdir.makeconftest(
        """
        def pytest_saltfactories_syndic_configuration_overrides():
            return {
                'zzzz': True
            }
        """
    )
    p = testdir.makepyfile(
        """
        def test_basic_config_override(request, salt_factories):
            mom_config = salt_factories.configure_master(request, 'mom-1')
            syndic_id = 'syndic-1'
            syndic_config = salt_factories.configure_syndic(request, syndic_id, master_of_masters_id='mom-1')
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(failed=1)
    res.stdout.fnmatch_lines(
        ["*RuntimeError: The config overrides returned by * must only contain 3 top level keys: *"]
    )


def test_keyword_basic_config_overrides_top_level_keys(request, salt_factories):
    with pytest.raises(RuntimeError) as exc:
        mom_config = salt_factories.configure_master(request, "mom-1")
        syndic_id = "syndic-1"
        syndic_config = salt_factories.configure_syndic(
            request, syndic_id, master_of_masters_id="mom-1", config_overrides={"zzzz": True}
        )

    assert re.match(
        r"The config_overrides keyword argument must only contain 3 top level keys: .*",
        str(exc.value),
    )


def test_hook_basic_config_defaults(testdir):
    testdir.makeconftest(
        """
        def pytest_saltfactories_syndic_configuration_defaults():
            return {
                'syndic': {'zzzz': True},
                'master': {'zzzz': True},
                'minion': {'zzzz': True},
            }
        """
    )
    p = testdir.makepyfile(
        """
        def test_basic_config_override(request, salt_factories):
            mom_config = salt_factories.configure_master(request, 'mom-1')
            syndic_id = 'syndic-1'
            syndic_config = salt_factories.configure_syndic(request, syndic_id, master_of_masters_id='mom-1')
            assert 'zzzz' in syndic_config
            assert syndic_config['zzzz'] is True
            syndic_master_config = salt_factories.configure_master(request, syndic_id)
            assert 'zzzz' in syndic_master_config
            assert syndic_master_config['zzzz'] is True
            syndic_minion_config = salt_factories.configure_minion(request, syndic_id)
            assert 'zzzz' in syndic_minion_config
            assert syndic_minion_config['zzzz'] is True
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(passed=1)


def test_keyword_basic_config_defaults(request, salt_factories):
    mom_config = salt_factories.configure_master(request, "mom-1")
    syndic_id = "syndic-1"
    config_defaults = {
        "syndic": {"zzzz": True},
        "master": {"zzzz": True},
        "minion": {"zzzz": True},
    }
    syndic_config = salt_factories.configure_syndic(
        request, syndic_id, master_of_masters_id="mom-1", config_defaults=config_defaults
    )
    assert "zzzz" in syndic_config
    assert syndic_config["zzzz"] is True
    syndic_master_config = salt_factories.configure_master(request, syndic_id)
    assert "zzzz" in syndic_master_config
    assert syndic_master_config["zzzz"] is True
    syndic_minion_config = salt_factories.configure_minion(request, syndic_id)
    assert "zzzz" in syndic_minion_config
    assert syndic_minion_config["zzzz"] is True


def test_hook_basic_config_overrides(testdir):
    testdir.makeconftest(
        """
        def pytest_saltfactories_syndic_configuration_overrides():
            return {
                'syndic': {'zzzz': True},
                'master': {'zzzz': True},
                'minion': {'zzzz': True},
            }
        """
    )
    p = testdir.makepyfile(
        """
        def test_basic_config_override(request, salt_factories):
            mom_config = salt_factories.configure_master(request, 'mom-1')
            syndic_id = 'syndic-1'
            syndic_config = salt_factories.configure_syndic(request, syndic_id, master_of_masters_id='mom-1')
            assert 'zzzz' in syndic_config
            assert syndic_config['zzzz'] is True
            syndic_master_config = salt_factories.configure_master(request, syndic_id)
            assert 'zzzz' in syndic_master_config
            assert syndic_master_config['zzzz'] is True
            syndic_minion_config = salt_factories.configure_minion(request, syndic_id)
            assert 'zzzz' in syndic_minion_config
            assert syndic_minion_config['zzzz'] is True
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(passed=1)


def test_keyword_basic_config_overrides(request, salt_factories):
    mom_config = salt_factories.configure_master(request, "mom-1")
    syndic_id = "syndic-1"
    config_overrides = {
        "syndic": {"zzzz": True},
        "master": {"zzzz": True},
        "minion": {"zzzz": True},
    }
    syndic_config = salt_factories.configure_syndic(
        request, syndic_id, master_of_masters_id="mom-1", config_overrides=config_overrides
    )
    assert "zzzz" in syndic_config
    assert syndic_config["zzzz"] is True
    syndic_master_config = salt_factories.configure_master(request, syndic_id)
    assert "zzzz" in syndic_master_config
    assert syndic_master_config["zzzz"] is True
    syndic_minion_config = salt_factories.configure_minion(request, syndic_id)
    assert "zzzz" in syndic_minion_config
    assert syndic_minion_config["zzzz"] is True


def test_hook_simple_overrides_override_defaults(testdir):
    testdir.makeconftest(
        """
        def pytest_saltfactories_syndic_configuration_defaults():
            return {
                'syndic': {'zzzz': False},
                'master': {'zzzz': False},
                'minion': {'zzzz': False},
            }

        def pytest_saltfactories_syndic_configuration_overrides():
            return {
                'syndic': {'zzzz': True},
                'master': {'zzzz': True},
                'minion': {'zzzz': True},
            }
        """
    )
    p = testdir.makepyfile(
        """
        def test_basic_config_override(request, salt_factories):
            mom_config = salt_factories.configure_master(request, 'mom-1')
            syndic_id = 'syndic-1'
            syndic_config = salt_factories.configure_syndic(request, syndic_id, master_of_masters_id='mom-1')
            assert 'zzzz' in syndic_config
            assert syndic_config['zzzz'] is True
            syndic_master_config = salt_factories.configure_master(request, syndic_id)
            assert 'zzzz' in syndic_master_config
            assert syndic_master_config['zzzz'] is True
            syndic_minion_config = salt_factories.configure_minion(request, syndic_id)
            assert 'zzzz' in syndic_minion_config
            assert syndic_minion_config['zzzz'] is True
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(passed=1)


def test_keyword_simple_overrides_override_defaults(request, salt_factories):
    mom_config = salt_factories.configure_master(request, "mom-1")
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
    syndic_config = salt_factories.configure_syndic(
        request,
        syndic_id,
        master_of_masters_id="mom-1",
        config_defaults=config_defaults,
        config_overrides=config_overrides,
    )
    assert "zzzz" in syndic_config
    assert syndic_config["zzzz"] is True
    syndic_master_config = salt_factories.configure_master(request, syndic_id)
    assert "zzzz" in syndic_master_config
    assert syndic_master_config["zzzz"] is True
    syndic_minion_config = salt_factories.configure_minion(request, syndic_id)
    assert "zzzz" in syndic_minion_config
    assert syndic_minion_config["zzzz"] is True


def test_hook_nested_overrides_override_defaults(testdir):
    testdir.makeconftest(
        """
        def pytest_saltfactories_syndic_configuration_defaults():
            defaults = {
                'zzzz': False,
                'user': 'foobar',
                'colors': {
                    'black': True,
                    'white': False
                }
            }
            return {
                'syndic': defaults.copy(),
                'master': defaults.copy(),
                'minion': defaults.copy(),
            }

        def pytest_saltfactories_syndic_configuration_overrides():
            overrides = {
                'zzzz': True,
                'colors': {
                    'white': True,
                    'grey': False
                }
            }
            return {
                'syndic': overrides.copy(),
                'master': overrides.copy(),
                'minion': overrides.copy(),
            }
        """
    )
    p = testdir.makepyfile(
        """
        def test_basic_config_override(request, salt_factories):
            expected_colors = {
                'black': True,
                'white': True,
                'grey': False
            }
            mom_config = salt_factories.configure_master(request, 'mom-1')
            syndic_id = 'syndic-1'
            syndic_config = salt_factories.configure_syndic(request, syndic_id, master_of_masters_id='mom-1')
            assert 'zzzz' in syndic_config
            assert syndic_config['zzzz'] is True
            assert syndic_config['colors'] == expected_colors
            syndic_master_config = salt_factories.configure_master(request, syndic_id)
            assert 'zzzz' in syndic_master_config
            assert syndic_master_config['zzzz'] is True
            assert syndic_master_config['colors'] == expected_colors
            syndic_minion_config = salt_factories.configure_minion(request, syndic_id)
            assert 'zzzz' in syndic_minion_config
            assert syndic_minion_config['zzzz'] is True
            assert syndic_minion_config['colors'] == expected_colors
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(passed=1)


def test_keyword_nested_overrides_override_defaults(request, salt_factories):
    defaults = {"zzzz": False, "user": "foobar", "colors": {"black": True, "white": False}}
    overrides = {"zzzz": True, "colors": {"white": True, "grey": False}}
    expected_colors = {"black": True, "white": True, "grey": False}
    mom_config = salt_factories.configure_master(request, "mom-1")
    syndic_id = "syndic-1"
    syndic_config = salt_factories.configure_syndic(
        request,
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
    )
    assert "zzzz" in syndic_config
    assert syndic_config["zzzz"] is True
    assert syndic_config["colors"] == expected_colors
    syndic_master_config = salt_factories.configure_master(request, syndic_id)
    assert "zzzz" in syndic_master_config
    assert syndic_master_config["zzzz"] is True
    assert syndic_master_config["colors"] == expected_colors
    syndic_minion_config = salt_factories.configure_minion(request, syndic_id)
    assert "zzzz" in syndic_minion_config
    assert syndic_minion_config["zzzz"] is True
    assert syndic_minion_config["colors"] == expected_colors


def test_nested_overrides_override_defaults(testdir):
    testdir.makeconftest(
        """
        def pytest_saltfactories_syndic_configuration_defaults():
            defaults = {
                'zzzz': None,
                'user': 'foobar',
                'colors': {
                    'blue': False
                }
            }
            return {
                'syndic': defaults.copy(),
                'master': defaults.copy(),
                'minion': defaults.copy(),
            }

        def pytest_saltfactories_syndic_configuration_overrides():
            overrides = {
                'zzzz': False,
                'colors': {
                    'blue': True
                }
            }
            return {
                'syndic': overrides.copy(),
                'master': overrides.copy(),
                'minion': overrides.copy(),
            }
        """
    )
    p = testdir.makepyfile(
        """
        def test_basic_config_override(request, salt_factories):
            defaults = {
                'colors': {
                    'black': True,
                    'white': False
                }
            }
            overrides = {
                'zzzz': True,
                'colors': {
                    'white': True,
                    'grey': False
                }
            }
            expected_colors = {
                'black': True,
                'white': True,
                'grey': False,
                'blue': True
            }
            mom_config = salt_factories.configure_master(request, 'mom-1')
            syndic_id = 'syndic-1'
            syndic_config = salt_factories.configure_syndic(
                request,
                syndic_id,
                master_of_masters_id='mom-1',
                config_defaults={
                    'syndic': defaults.copy(),
                    'master': defaults.copy(),
                    'minion': defaults.copy(),
                },
                config_overrides={
                    'syndic': overrides.copy(),
                    'master': overrides.copy(),
                    'minion': overrides.copy(),
                }
            )
            assert 'zzzz' in syndic_config
            assert syndic_config['zzzz'] is True
            assert syndic_config['colors'] == expected_colors
            syndic_master_config = salt_factories.configure_master(request, syndic_id)
            assert 'zzzz' in syndic_master_config
            assert syndic_master_config['zzzz'] is True
            assert syndic_master_config['colors'] == expected_colors
            syndic_minion_config = salt_factories.configure_minion(request, syndic_id)
            assert 'zzzz' in syndic_minion_config
            assert syndic_minion_config['zzzz'] is True
            assert syndic_minion_config['colors'] == expected_colors
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(passed=1)


def test_provide_root_dir(testdir, request, salt_factories):
    mom_config = salt_factories.configure_master(request, "mom-1")
    root_dir = testdir.mkdir("custom-root")
    config_defaults = {
        "syndic": {"root_dir": root_dir},
    }
    syndic_id = "syndic-1"
    syndic_config = salt_factories.configure_syndic(
        request, syndic_id, master_of_masters_id="mom-1", config_defaults=config_defaults
    )
    syndic_config = salt_factories.configure_syndic(
        request, "syndic-1", config_defaults=config_defaults
    )
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
def test_provide_user(request, salt_factories, configure_kwargs):
    mom_config = salt_factories.configure_master(request, "mom-1")
    configure_syndic_kwargs = configure_kwargs.copy()
    configure_syndic_kwargs["master_of_masters_id"] = "mom-1"

    syndic_id = "syndic-1"
    syndic_config = salt_factories.configure_syndic(request, syndic_id, **configure_syndic_kwargs)

    if not configure_kwargs:
        # salt-factories injects the current username
        master_config = salt_factories.cache["configs"]["masters"][syndic_id]
        assert master_config["user"] is not None
        assert master_config["user"] == salt_factories.get_running_username()
        minion_config = salt_factories.cache["configs"]["minions"][syndic_id]
        assert minion_config["user"] is not None
        assert minion_config["user"] == salt_factories.get_running_username()
        assert syndic_config["user"] is not None
        assert syndic_config["user"] == salt_factories.get_running_username()
    else:
        master_config = salt_factories.cache["configs"]["masters"][syndic_id]
        assert master_config["user"] != salt_factories.get_running_username()
        assert master_config["user"] == "blah"
        minion_config = salt_factories.cache["configs"]["minions"][syndic_id]
        assert minion_config["user"] != salt_factories.get_running_username()
        assert minion_config["user"] == "blah"
        # salt-factories does not override the passed user value
        assert syndic_config["user"] != salt_factories.get_running_username()
        assert syndic_config["user"] == "blah"
