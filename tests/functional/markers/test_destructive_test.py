"""
    tests.functional.markers.test_destructive_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the ``@pytest.mark.destructive_test`` marker
"""
import pytest


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
    try:
        res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")
    except AttributeError:  # pragma: no cover
        # PyTest 4.6.x
        from _pytest.outcomes import Failed

        with pytest.raises(Failed):
            res.stdout.fnmatch_lines(
                ["*PytestUnknownMarkWarning*",]
            )


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
    try:
        res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")
    except AttributeError:  # pragma: no cover
        # PyTest 4.6.x
        from _pytest.outcomes import Failed

        with pytest.raises(Failed):
            res.stdout.fnmatch_lines(
                ["*PytestUnknownMarkWarning*",]
            )
