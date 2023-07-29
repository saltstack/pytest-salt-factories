# pylint: disable=no-member
import logging
from unittest.mock import patch

import pytest

import saltfactories

try:
    saltfactories.__salt__  # pylint: disable=pointless-statement
    HAS_SALT_DUNDER = True  # pragma: no cover
except AttributeError:
    HAS_SALT_DUNDER = False


log = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def _confirm_saltfactories_does_not_have_salt_dunders():
    assert (
        HAS_SALT_DUNDER is False
    ), "Weirdly, the saltfactories module has a __salt__ dunder defined. That's a bug!"


@pytest.fixture
def pre_loader_modules_patched_fixture():
    with pytest.raises(AttributeError):
        assert isinstance(saltfactories.__salt__, dict)
    try:
        yield False
    finally:
        with pytest.raises(AttributeError):
            assert isinstance(saltfactories.__salt__, dict)


@pytest.fixture
def configure_loader_modules(pre_loader_modules_patched_fixture):
    return {
        saltfactories: {
            "__salt__": {"test.echo": lambda x: x, "foo": pre_loader_modules_patched_fixture}
        }
    }


@pytest.fixture
def _fixture_that_needs_loader_modules_patched():
    assert saltfactories.__salt__["foo"] is False
    try:
        with patch.dict(saltfactories.__salt__, {"foo": True}):
            assert saltfactories.__salt__["foo"] is True
            yield
    finally:
        assert saltfactories.__salt__["foo"] is False


@pytest.mark.usefixtures("_fixture_that_needs_loader_modules_patched")
@pytest.mark.parametrize(
    "retval",
    # These values are equal and only serve the purpose of running the same test
    # twice. If patching fails to cleanup the added module globals, the second
    # time the test runs the _fixture_that_needs_loader_modules_patched will
    # fail it's assertions
    [True, True],
)
def test_fixture_deps(retval):
    assert saltfactories.__salt__["foo"] is retval
    assert saltfactories.__salt__["test.echo"]("foo") == "foo"
