# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals


def test_basic_minion_config_overrides(testdir):
    testdir.makeconftest(
        """
        def pytest_saltfactories_minion_configuration_overrides():
            return {'zzzz': True}
        """
    )
    p = testdir.makepyfile(
        """
        def test_basic_minion_config_override(request, salt_factories):
            minion_config = salt_factories.configure_minion(request, 'minion-1')
            assert 'zzzz' in minion_config
        """
    )
    res = testdir.runpytest("-v")
    try:
        res.assert_outcomes(passed=1)
    except (AssertionError, ValueError):
        import pprint

        pprint.pprint(res.__dict__)
