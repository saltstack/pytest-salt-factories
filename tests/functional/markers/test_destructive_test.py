"""
    tests.functional.markers.test_destructive_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the ``@pytest.mark.destructive_test`` marker
"""


def test_run_destructive_skipped(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.destructive_test
        def test_one():
            assert True
        """
    )
    res = testdir.runpytest()
    res.assert_outcomes(skipped=1)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")


def test_run_destructive_not_skipped(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.destructive_test
        def test_one():
            assert True
        """
    )
    res = testdir.runpytest("--run-destructive")
    res.assert_outcomes(passed=1)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")
