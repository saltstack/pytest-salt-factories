"""
    tests.functional.markers.test_skip_on_spawning_platform
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the ``@pytest.mark.skip_on_spawning_platform`` marker
"""
from unittest import mock


def test_skipped(pytester):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.skip_on_spawning_platform
        def test_one():
            assert True
        """
    )
    with mock.patch("saltfactories.utils.platform.is_spawning_platform", return_value=True):
        res = pytester.runpytest_inprocess()
        res.assert_outcomes(skipped=1)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")


def test_not_skipped(pytester):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.skip_on_spawning_platform
        def test_one():
            assert True
        """
    )
    with mock.patch("saltfactories.utils.platform.is_spawning_platform", return_value=False):
        res = pytester.runpytest_inprocess()
        res.assert_outcomes(passed=1)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")


def test_skip_reason(pytester):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.skip_on_spawning_platform(reason='Because!')
        def test_one():
            assert True
        """
    )
    with mock.patch("saltfactories.utils.platform.is_spawning_platform", return_value=True):
        res = pytester.runpytest_inprocess("-ra", "-s", "-vv")
        res.assert_outcomes(skipped=1)
    res.stdout.fnmatch_lines(["SKIPPED * test_skip_reason.py:*: Because!"])
