"""
    tests.functional.utils.test_loader
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Salt loader mock related tests
"""
import pytest


def test_runtime_error_raised_for_non_module_type_keys(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture
        def configure_loader_modules():
            return {"foobar": {}}

        def test_one():
            assert True
        """
    )
    res = testdir.runpytest()
    res.assert_outcomes(errors=1)
    res.stdout.fnmatch_lines(
        [
            "*RuntimeError: The dictionary keys returned by setup_loader_modules() must be an imported module*"
        ]
    )


def test_runtime_error_raised_for_non_dict_values(testdir):
    testdir.makepyfile(
        """
        import pytest
        import string

        @pytest.fixture
        def configure_loader_modules():
            return {string: "yes"}

        def test_one():
            assert True
        """
    )
    res = testdir.runpytest()
    res.assert_outcomes(errors=1)
    res.stdout.fnmatch_lines(
        [
            "*RuntimeError: The dictionary values returned by setup_loader_modules() must be a dictionary*"
        ]
    )


def test_runtime_error_raised_for_bad_fixture_name(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture
        def configure_loader_module():
            return {"foobar": {}}

        def test_one():
            assert True
        """
    )
    res = testdir.runpytest()
    res.stdout.fnmatch_lines(
        [
            "*RuntimeError:*defines a 'configure_loader_module' fixture but the "
            "correct fixture name is 'configure_loader_modules'*"
        ]
    )


def test_bad_fixture_name_as_plain_function_ok(testdir):
    testdir.makepyfile(
        """
        import pytest
        import string

        def configure_loader_module():
            return {"foobar": {}}

        @pytest.fixture
        def configure_loader_modules():
            return {string: {}}

        def test_one():
            assert True
        """
    )
    res = testdir.runpytest()
    res.assert_outcomes(passed=1)


def test_runtime_error_raised_when_sys_modules_is_not_list(testdir):
    testdir.makepyfile(
        """
        import pytest
        import string

        @pytest.fixture
        def configure_loader_modules():
            return {string: {"sys.modules": False}, "sys.modules": True}

        def test_one():
            assert True
        """
    )
    res = testdir.runpytest()
    res.assert_outcomes(errors=1)
    res.stdout.fnmatch_lines(["*RuntimeError: 'sys.modules' must be a dictionary*"])


@pytest.mark.parametrize("dunder", ["__virtual__", "__init__"])
def test_runtime_error_raised_when_not_needed_dunders_are_passed(testdir, dunder):
    testdir.makepyfile(
        """
        import pytest
        import string

        @pytest.fixture
        def configure_loader_modules():
            return {{string: {{"{}": False}}}}

        def test_one():
            assert True
        """.format(
            dunder
        )
    )
    res = testdir.runpytest()
    res.assert_outcomes(errors=1)
    res.stdout.fnmatch_lines(["*RuntimeError: No need to patch '{}'*".format(dunder)])


def test_runtime_error_raised_on_unknown_salt_dunders(testdir):
    testdir.makepyfile(
        """
        import pytest
        import string

        @pytest.fixture
        def configure_loader_modules():
            return {string: {"__foobar__": False}}

        def test_one():
            assert True
        """
    )
    res = testdir.runpytest()
    res.assert_outcomes(errors=1)
    res.stdout.fnmatch_lines(["*RuntimeError: Don't know how to handle '__foobar__'*"])
