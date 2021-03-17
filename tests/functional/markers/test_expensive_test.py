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
