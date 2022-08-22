import logging
from unittest.mock import patch

import pytest

import saltfactories

try:
    saltfactories.__salt__  # pylint: disable=pointless-statement
    HAS_SALT_DUNDER = True
except AttributeError:
    HAS_SALT_DUNDER = False

log = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def confirm_saltfactories_does_not_have_salt_dunders():
    assert (
        HAS_SALT_DUNDER is False
    ), "Weirdly, the saltfactories module has a __salt__ dunder defined. That's a bug!"


def confirm_saltfactories_does_not_have_salt_dunders_after_setup_loader_mock_terminates(
    setup_loader_mock,
):
    yield
    with pytest.raises(AttributeError):
        assert isinstance(saltfactories.__salt__, dict)  # pylint: disable=no-member


@pytest.fixture
def pre_loader_modules_patched_fixture():
    with pytest.raises(AttributeError):
        assert isinstance(saltfactories.__salt__, dict)  # pylint: disable=no-member
    yield False


@pytest.fixture
def configure_loader_modules(pre_loader_modules_patched_fixture):
    return {
        saltfactories: {
            "__salt__": {"test.echo": lambda x: x, "foo": pre_loader_modules_patched_fixture}
        }
    }


@pytest.fixture
def fixture_that_needs_loader_modules_patched():
    assert saltfactories.__salt__["foo"] is False  # pylint: disable=no-member
    with patch.dict(saltfactories.__salt__, {"foo": True}):  # pylint: disable=no-member
        assert saltfactories.__salt__["foo"] is True  # pylint: disable=no-member
        yield
    assert saltfactories.__salt__["foo"] is False  # pylint: disable=no-member


def test_fixture_deps(fixture_that_needs_loader_modules_patched):
    assert saltfactories.__salt__["foo"] is True  # pylint: disable=no-member
    assert saltfactories.__salt__["test.echo"]("foo") == "foo"  # pylint: disable=no-member
