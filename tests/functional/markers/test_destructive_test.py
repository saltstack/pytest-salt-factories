"""
    tests.functional.markers.test_destructive_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the ``@pytest.mark.destructive_test`` marker
"""


def test_run_destructive_skipped(pytester):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.destructive_test
        def test_one():
            assert True
        """
    )
    res = pytester.runpytest()
    res.assert_outcomes(skipped=1)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")


def test_run_destructive_not_skipped(pytester):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.destructive_test
        def test_one():
            assert True
        """
    )
    res = pytester.runpytest("--run-destructive")
    res.assert_outcomes(passed=1)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")


def test_error_on_args_or_kwargs(pytester):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.destructive_test("arg")
        def test_one():
            assert True

        @pytest.mark.destructive_test(kwarg="arg")
        def test_two():
            assert True
        """
    )
    res = pytester.runpytest("--run-destructive")
    res.assert_outcomes(errors=2)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")
    res.stdout.fnmatch_lines(
        [
            "*UsageError: The 'destructive_test' marker does not accept any arguments or keyword arguments*"
        ]
    )
