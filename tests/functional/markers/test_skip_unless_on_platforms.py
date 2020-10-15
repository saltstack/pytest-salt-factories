"""
    tests.functional.markers.test_skip_unless_on_platforms
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the ``@pytest.mark.skip_unless_on_platforms`` marker
"""
from unittest import mock

import pytest


@pytest.mark.parametrize(
    "platform",
    ["windows", "linux", "darwin", "sunos", "smartos", "freebsd", "netbsd", "openbsd", "aix"],
)
def test_skipped(testdir, platform):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.skip_unless_on_platforms({}=True)
        def test_one():
            assert True
        """.format(
            platform
        )
    )
    return_value = False
    with mock.patch(
        "saltfactories.utils.platform.is_{}".format(platform), return_value=return_value
    ):
        res = testdir.runpytest_inprocess()
        res.assert_outcomes(skipped=1)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")


@pytest.mark.parametrize(
    "platform",
    ["windows", "linux", "darwin", "sunos", "smartos", "freebsd", "netbsd", "openbsd", "aix"],
)
def test_not_skipped(testdir, platform):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.skip_unless_on_platforms({}=True)
        def test_one():
            assert True
        """.format(
            platform
        )
    )
    return_value = True
    with mock.patch(
        "saltfactories.utils.platform.is_{}".format(platform), return_value=return_value
    ):
        res = testdir.runpytest_inprocess()
        res.assert_outcomes(passed=1)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")


def test_skip_reason(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.skip_unless_on_platforms(windows=True, reason='Because!')
        def test_one():
            assert True
        """
    )
    return_value = False
    with mock.patch("saltfactories.utils.platform.is_windows", return_value=return_value):
        res = testdir.runpytest_inprocess("-ra", "-s", "-vv")
        res.assert_outcomes(skipped=1)
    res.stdout.fnmatch_lines(["SKIPPED * test_skip_reason.py:*: Because!"])


def test_no_platforms(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.skip_unless_on_platforms
        def test_one():
            assert True
        """
    )
    res = testdir.runpytest_inprocess()
    res.stdout.fnmatch_lines(
        [
            "* RuntimeError: Pass at least one platform to skip_unless_on_platforms as a keyword argument"
        ]
    )


def test_all_platforms_false(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.skip_unless_on_platforms(windows=False, linux=False)
        def test_one():
            assert True
        """
    )
    res = testdir.runpytest_inprocess()
    res.stdout.fnmatch_lines(
        [
            "* RuntimeError: Pass at least one platform with a True value to skip_unless_on_platforms as a keyword argument"
        ]
    )


def test_unknown_platform(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.skip_unless_on_platforms(car=True)
        def test_one():
            assert True
        """
    )
    res = testdir.runpytest_inprocess()
    res.stdout.fnmatch_lines(
        [
            "* RuntimeError: Passed an invalid platform to skip_unless_on_platforms: on_platforms() got an unexpected keyword argument 'car'"
        ]
    )
