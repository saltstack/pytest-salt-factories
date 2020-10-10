"""
    tests.functional.markers.test_skip_on_netbsd
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the ``@pytest.mark.skip_on_netbsd`` marker
"""
from unittest import mock


def test_skipped(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.skip_on_netbsd
        def test_one():
            assert True
        """
    )
    return_value = True
    with mock.patch("saltfactories.utils.platform.is_netbsd", return_value=return_value):
        res = testdir.runpytest_inprocess()
        res.assert_outcomes(skipped=1)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")


def test_not_skipped(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.skip_on_netbsd
        def test_one():
            assert True
        """
    )
    return_value = False
    with mock.patch("saltfactories.utils.platform.is_netbsd", return_value=return_value):
        res = testdir.runpytest_inprocess()
        res.assert_outcomes(passed=1)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")


def test_skip_reason(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.skip_on_netbsd(reason='Because!')
        def test_one():
            assert True
        """
    )
    return_value = True
    with mock.patch("saltfactories.utils.platform.is_netbsd", return_value=return_value):
        res = testdir.runpytest_inprocess("-ra", "-s", "-vv")
        res.assert_outcomes(skipped=1)
    res.stdout.fnmatch_lines(["SKIPPED * test_skip_reason.py:*: Because!"])
