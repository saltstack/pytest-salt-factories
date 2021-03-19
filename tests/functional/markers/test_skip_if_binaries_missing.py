"""
    tests.functional.markers.test_skip_if_binaries_missing
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the ``@pytest.mark.skip_if_binaries_missing`` marker
"""


def test_skipped(pytester):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.skip_if_binaries_missing("python9")
        def test_one():
            assert True
        """
    )
    res = pytester.runpytest()
    res.assert_outcomes(skipped=1)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")


def test_skipped_multiple_binaries(pytester):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.skip_if_binaries_missing("python", "python9", check_all=True)
        def test_one():
            assert True
        """
    )
    res = pytester.runpytest()
    res.assert_outcomes(skipped=1)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")


def test_not_skipped(pytester):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.skip_if_binaries_missing("python")
        def test_one():
            assert True
        """
    )
    res = pytester.runpytest_inprocess("-ra", "-vv")
    res.assert_outcomes(passed=1)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")


def test_not_skipped_multiple_binaries(pytester):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.skip_if_binaries_missing("python", "pip")
        def test_one():
            assert True
        """
    )
    res = pytester.runpytest_inprocess("-ra", "-vv")
    res.assert_outcomes(passed=1)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")
