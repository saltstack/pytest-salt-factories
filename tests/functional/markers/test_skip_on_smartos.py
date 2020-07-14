"""
    tests.functional.markers.test_skip_on_smartos
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the ``@pytest.mark.skip_on_smartos`` marker
"""
from unittest import mock

import pytest


def test_skipped(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.skip_on_smartos
        def test_one():
            assert True
        """
    )
    return_value = True
    with mock.patch("saltfactories.utils.platform.is_smartos", return_value=return_value):
        res = testdir.runpytest_inprocess()
        res.assert_outcomes(skipped=1)
    try:
        res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")
    except AttributeError:  # pragma: no cover
        # PyTest 4.6.x
        from _pytest.outcomes import Failed

        with pytest.raises(Failed):
            res.stdout.fnmatch_lines(
                ["*PytestUnknownMarkWarning*",]
            )


def test_not_skipped(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.skip_on_smartos
        def test_one():
            assert True
        """
    )
    return_value = False
    with mock.patch("saltfactories.utils.platform.is_smartos", return_value=return_value):
        res = testdir.runpytest_inprocess()
        res.assert_outcomes(passed=1)
    try:
        res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")
    except AttributeError:  # pragma: no cover
        # PyTest 4.6.x
        from _pytest.outcomes import Failed

        with pytest.raises(Failed):
            res.stdout.fnmatch_lines(
                ["*PytestUnknownMarkWarning*",]
            )


def test_skip_reason(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.skip_on_smartos(reason='Because!')
        def test_one():
            assert True
        """
    )
    return_value = True
    with mock.patch("saltfactories.utils.platform.is_smartos", return_value=return_value):
        res = testdir.runpytest_inprocess("-ra", "-s", "-vv")
        res.assert_outcomes(skipped=1)
    res.stdout.fnmatch_lines(["SKIPPED * test_skip_reason.py:*: Because!"])
