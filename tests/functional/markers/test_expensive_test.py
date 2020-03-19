# -*- coding: utf-8 -*-
"""
    tests.functional.markers.test_expensive_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the ``@pytest.mark.expensive_test`` marker
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import pytest


def test_run_expensive_skipped(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.expensive_test
        def test_one():
            assert True
        """
    )
    res = testdir.runpytest()
    res.assert_outcomes(skipped=1)
    try:
        res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")
    except AttributeError:
        # PyTest 4.6.x
        from _pytest.outcomes import Failed

        with pytest.raises(Failed):
            res.stdout.fnmatch_lines(
                ["*PytestUnknownMarkWarning*",]
            )


def test_run_expensive_not_skipped(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.expensive_test
        def test_one():
            assert True
        """
    )
    res = testdir.runpytest("--run-expensive")
    res.assert_outcomes(passed=1)
    try:
        res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")
    except AttributeError:
        # PyTest 4.6.x
        from _pytest.outcomes import Failed

        with pytest.raises(Failed):
            res.stdout.fnmatch_lines(
                ["*PytestUnknownMarkWarning*",]
            )
