import pytest

import saltfactories

try:
    saltfactories.__salt__  # pylint: disable=pointless-statement
    HAS_SALT_DUNDER = True
except AttributeError:
    HAS_SALT_DUNDER = False


@pytest.fixture
def configure_loader_modules():
    return {saltfactories: {"__salt__": {"test.echo": lambda x: x}}}


def test_loader_mocking():
    assert (
        HAS_SALT_DUNDER is False
    ), "Weirdly, the saltfactories module has a __salt__ dunder defined. That's a bug!"
    # The saltfactories.__init__ module DOES NOT have a __salt__ dunder defined
    # So, if the assert bellow works, it means that the loader mocking works.
    assert "test.echo" in saltfactories.__salt__
    assert saltfactories.__salt__["test.echo"]("foo") == "foo"


def test_loader_mocking_through_runpytest(pytester):
    pytester.makepyfile(
        """
        import pytest
        import saltfactories

        @pytest.fixture
        def configure_loader_modules():
            return {saltfactories: {"__salt__": {"test.echo": lambda x: x}}}

        def test_one():
            assert saltfactories.__salt__["test.echo"]("foo") == "foo"
        """
    )
    res = pytester.runpytest()
    res.assert_outcomes(passed=1)


def test_runtime_error_raised_for_non_module_type_keys(pytester):
    pytester.makepyfile(
        """
        import pytest

        @pytest.fixture
        def configure_loader_modules():
            return {"foobar": {}}

        def test_one():
            assert True
        """
    )
    res = pytester.runpytest()
    res.assert_outcomes(errors=1)
    res.stdout.fnmatch_lines(
        [
            "*UsageError: The dictionary keys returned by setup_loader_modules() must be an imported module*"
        ]
    )


def test_runtime_error_raised_for_non_dict_values(pytester):
    pytester.makepyfile(
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
    res = pytester.runpytest()
    res.assert_outcomes(errors=1)
    res.stdout.fnmatch_lines(
        [
            "*UsageError: The dictionary values returned by setup_loader_modules() must be a dictionary*"
        ]
    )


def test_runtime_error_raised_when_sys_modules_is_not_list(pytester):
    pytester.makepyfile(
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
    res = pytester.runpytest()
    res.assert_outcomes(errors=1)
    res.stdout.fnmatch_lines(["*UsageError: 'sys.modules' must be a dictionary*"])


@pytest.mark.parametrize("dunder", ["__virtual__", "__init__"])
def test_runtime_error_raised_when_not_needed_dunders_are_passed(pytester, dunder):
    pytester.makepyfile(
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
    res = pytester.runpytest()
    res.assert_outcomes(errors=1)
    res.stdout.fnmatch_lines(["*UsageError: No need to patch '{}'*".format(dunder)])


def test_runtime_error_raised_on_unknown_salt_dunders(pytester):
    pytester.makepyfile(
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
    res = pytester.runpytest()
    res.assert_outcomes(errors=1)
    res.stdout.fnmatch_lines(["*UsageError: Don't know how to handle '__foobar__'*"])


def test_configure_loader_modules_not_a_fixture(pytester):
    pytester.makepyfile(
        """
        import pytest
        import saltfactories

        def configure_loader_modules():
            return {saltfactories: {"__salt__": {"test.echo": lambda x: x}}}

        def test_one():
            assert True
        """
    )
    res = pytester.runpytest()
    res.stdout.fnmatch_lines(
        [
            "*RuntimeError:*defines a 'configure_loader_modules' function but that function is not a fixture*"
        ]
    )


def test_runtime_error_raised_for_bad_fixture_name(pytester):
    pytester.makepyfile(
        """
        import pytest

        @pytest.fixture
        def configure_loader_module():
            return {"foobar": {}}

        def test_one():
            assert True
        """
    )
    res = pytester.runpytest()
    res.stdout.fnmatch_lines(
        [
            "*RuntimeError:*defines a 'configure_loader_module' fixture but the "
            "correct fixture name is 'configure_loader_modules'*"
        ]
    )


def test_bad_fixture_name_as_plain_function_ok(pytester):
    pytester.makepyfile(
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
    res = pytester.runpytest()
    res.assert_outcomes(passed=1)
