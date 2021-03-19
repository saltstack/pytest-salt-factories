"""
    tests.functional.markers.test_expensive_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the ``@pytest.mark.expensive_test`` marker
"""


def test_run_expensive_skipped(pytester):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.expensive_test
        def test_one():
            assert True
        """
    )
    res = pytester.runpytest()
    res.assert_outcomes(skipped=1)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")


def test_run_expensive_not_skipped(pytester):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.expensive_test
        def test_one():
            assert True
        """
    )
    res = pytester.runpytest("--run-expensive")
    res.assert_outcomes(passed=1)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")


def test_error_on_args_or_kwargs(pytester):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.expensive_test("arg")
        def test_one():
            assert True

        @pytest.mark.expensive_test(kwarg="arg")
        def test_two():
            assert True
        """
    )
    res = pytester.runpytest("--run-destructive")
    res.assert_outcomes(errors=2)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")
    res.stdout.fnmatch_lines(
        [
            "*UsageError: The 'expensive_test' marker does not accept any arguments or keyword arguments*"
        ]
    )
