"""
    tests.functional.markers.test_skip_if_not_root
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the ``@pytest.mark.skip_if_not_root`` marker
"""
import sys
from unittest import mock


def test_skip_if_not_root_skipped(pytester):
    pytester.makepyfile(
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
        res = pytester.runpytest()
        res.assert_outcomes(skipped=1)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")


def test_skip_if_not_root_not_skipped(pytester):
    pytester.makepyfile(
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
        res = pytester.runpytest_inprocess("-ra", "-vv")
        res.assert_outcomes(passed=1)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")


def test_error_on_args_or_kwargs(pytester):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.skip_if_not_root("arg")
        def test_one():
            assert True

        @pytest.mark.skip_if_not_root(kwarg="arg")
        def test_two():
            assert True
        """
    )
    res = pytester.runpytest("--run-destructive")
    res.assert_outcomes(errors=2)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")
    res.stdout.fnmatch_lines(
        [
            "*UsageError: The 'skip_if_not_root' marker does not accept any arguments or keyword arguments*"
        ]
    )
