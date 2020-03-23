# -*- coding: utf-8 -*-
"""
    tests.functional.markers.test_skip_if_not_root
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the ``@pytest.mark.skip_if_not_root`` marker
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import sys

import mock
import pytest


def test_skip_if_not_root_skipped(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.skip_if_not_root
        def test_one():
            assert True
        """
    )
    if not sys.platform.startswith("win"):
        mocked_func = mock.patch("os.getuid", return_value=1000)
    else:
        mocked_func = mock.patch("salt.utils.win_functions.is_admin", return_value=False)

    with mocked_func:
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


def test_skip_if_not_root_not_skipped(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.skip_if_not_root
        def test_one():
            assert True
        """
    )
    if not sys.platform.startswith("win"):
        mocked_func = mock.patch("os.getuid", return_value=0)
    else:
        mocked_func = mock.patch("salt.utils.win_functions.is_admin", return_value=True)

    with mocked_func:
        res = testdir.runpytest_inprocess("-ra", "-vv")
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
