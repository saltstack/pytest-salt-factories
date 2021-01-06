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


def test_loader_mocking_through_runpytest(testdir):
    testdir.makepyfile(
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
    res = testdir.runpytest()
    res.assert_outcomes(passed=1)


def test_configure_loader_modules_not_a_fixture(testdir):
    testdir.makepyfile(
        """
        import pytest
        import saltfactories

        def configure_loader_modules():
            return {saltfactories: {"__salt__": {"test.echo": lambda x: x}}}

        def test_one():
            assert True
        """
    )
    res = testdir.runpytest()
    # res.assert_outcomes(passed=1)
    res.stdout.fnmatch_lines(
        [
            "*RuntimeError*defines a configure_loader_modules function but that function is not a fixture*"
        ]
    )
