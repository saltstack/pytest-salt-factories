# -*- coding: utf-8 -*-
"""
    tests.functional.factories.test_proxy_minion_factory
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Functional tests for the salt proxy minion factory
"""
# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals


def test_hook_basic_config_defaults(testdir):
    testdir.makeconftest(
        """
        def pytest_saltfactories_proxy_minion_configuration_defaults():
            return {'zzzz': True}
        """
    )
    p = testdir.makepyfile(
        """
        def test_basic_config_override(request, salt_factories):
            proxy_minion_config = salt_factories.configure_proxy_minion(request, 'proxy-minion-1')
            assert 'zzzz' in proxy_minion_config
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(passed=1)


def test_keyword_basic_config_defaults(testdir):
    p = testdir.makepyfile(
        """
        def test_basic_config_override(request, salt_factories):
            proxy_minion_config = salt_factories.configure_proxy_minion(request, 'proxy-minion-1', config_defaults={'zzzz': True})
            assert 'zzzz' in proxy_minion_config
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(passed=1)


def test_hook_basic_config_overrides(testdir):
    testdir.makeconftest(
        """
        def pytest_saltfactories_proxy_minion_configuration_overrides():
            return {'zzzz': True}
        """
    )
    p = testdir.makepyfile(
        """
        def test_basic_config_override(request, salt_factories):
            proxy_minion_config = salt_factories.configure_proxy_minion(request, 'proxy-minion-1')
            assert 'zzzz' in proxy_minion_config
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(passed=1)


def test_keyword_basic_config_overrides(testdir):
    p = testdir.makepyfile(
        """
        def test_basic_config_override(request, salt_factories):
            proxy_minion_config = salt_factories.configure_proxy_minion(request, 'proxy-minion-1', config_overrides={'zzzz': True})
            assert 'zzzz' in proxy_minion_config
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(passed=1)


def test_hook_simple_overrides_override_defaults(testdir):
    testdir.makeconftest(
        """
        def pytest_saltfactories_proxy_minion_configuration_defaults():
            return {'zzzz': False}

        def pytest_saltfactories_proxy_minion_configuration_overrides():
            return {'zzzz': True}
        """
    )
    p = testdir.makepyfile(
        """
        def test_basic_config_override(request, salt_factories):
            proxy_minion_config = salt_factories.configure_proxy_minion(request, 'proxy-minion-1')
            assert 'zzzz' in proxy_minion_config
            assert proxy_minion_config['zzzz'] is True
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(passed=1)


def test_keyword_simple_overrides_override_defaults(testdir):
    p = testdir.makepyfile(
        """
        def test_basic_config_override(request, salt_factories):
            proxy_minion_config = salt_factories.configure_proxy_minion(
                request,
                'proxy-minion-1',
                config_defaults={'zzzz': False},
                config_overrides={'zzzz': True}
            )
            assert 'zzzz' in proxy_minion_config
            assert proxy_minion_config['zzzz'] is True
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(passed=1)


def test_hook_nested_overrides_override_defaults(testdir):
    testdir.makeconftest(
        """
        def pytest_saltfactories_proxy_minion_configuration_defaults():
            return {
                'zzzz': False,
                'user': 'foobar',
                'colors': {
                    'black': True,
                    'white': False
                }
            }

        def pytest_saltfactories_proxy_minion_configuration_overrides():
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
            proxy_minion_config = salt_factories.configure_proxy_minion(request, 'proxy-minion-1')
            assert 'zzzz' in proxy_minion_config
            assert proxy_minion_config['zzzz'] is False
            assert proxy_minion_config['colors'] == {
                'black': True,
                'white': True,
                'grey': False
            }
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(passed=1)


def test_keyword_nested_overrides_override_defaults(testdir):
    p = testdir.makepyfile(
        """
        def test_basic_config_override(request, salt_factories):
            proxy_minion_config = salt_factories.configure_proxy_minion(
                request,
                'proxy-minion-1',
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
            assert 'zzzz' in proxy_minion_config
            assert proxy_minion_config['zzzz'] is False
            assert proxy_minion_config['colors'] == {
                'black': True,
                'white': True,
                'grey': False
            }
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(passed=1)


def test_nested_overrides_override_defaults(testdir):
    testdir.makeconftest(
        """
        def pytest_saltfactories_proxy_minion_configuration_defaults():
            return {
                'zzzz': True,
                'user': 'foobar',
                'colors': {
                    'black': False,
                    'white': True,
                    'blue': False
                }
            }

        def pytest_saltfactories_proxy_minion_configuration_overrides():
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
            proxy_minion_config = salt_factories.configure_proxy_minion(
                request,
                'proxy-minion-1',
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
            assert 'zzzz' in proxy_minion_config
            assert proxy_minion_config['zzzz'] is False
            assert proxy_minion_config['colors'] == {
                'black': True,
                'white': True,
                'grey': False,
                'blue': True
            }
        """
    )
    res = testdir.runpytest("-v")
    res.assert_outcomes(passed=1)
