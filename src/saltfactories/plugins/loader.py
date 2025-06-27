"""
Salt loader mock support for tests.
"""
import logging

import pytest

from saltfactories.utils.loader import LoaderModuleMock

try:
    from _pytest.fixtures import FixtureFunctionDefinition
except ImportError:
    FixtureFunctionDefinition = None

log = logging.getLogger(__name__)


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(items):
    """
    Modify the collected items.

    Iterate through the collected items, in particular their test modules, to see if there's a function
    named ``configure_loader_modules``. If there is, assert that it's a fixture. If not, raise an error.
    """
    seen_modules = set()
    for item in items:
        if item.module.__name__ in seen_modules:
            # No need to check the same module more than once
            continue
        seen_modules.add(item.module.__name__)
        # Some users have reported that this was not working and it was due to the fixture having the
        # wrong name. Let's look for typos.
        typos = ("configure_loader_module", "configure_load_module", "configure_load_modules")
        for typo in typos:
            try:
                fixture = getattr(item.module, typo)
                if not _verify_fixture(fixture):
                    # It's a regular function?!
                    # Carry on
                    continue
                msg = (
                    f"The module {item.module} defines a '{typo}' fixture but the correct fixture "
                    "name is 'configure_loader_modules'"
                )
                raise RuntimeError(msg)
            except AttributeError:
                # The test module does not define a function with the typo as the name. Good.
                pass
        # If the test module defines a configure_loader_modules function, let's confirm that it's actually a fixture
        try:
            fixture = item.module.configure_loader_modules
        except AttributeError:
            # The test module does not define a `configure_loader_modules` function at all
            continue
        else:
            # The test module defines a `configure_loader_modules` function. Is it a fixture?
            if _verify_fixture(fixture):
                continue
            # It's not a fixture, raise an error
            msg = (
                f"The module {item.module} defines a 'configure_loader_modules' function but "
                "that function is not a fixture"
            )
            raise RuntimeError(msg) from None


def _verify_fixture(func):
    if FixtureFunctionDefinition is not None:
        # pytest 8.4+
        return isinstance(func, FixtureFunctionDefinition)
    return hasattr(func, "_pytestfixturefunction")


@pytest.fixture(autouse=True)
def setup_loader_mock(request):
    """
    Setup Salt's loader mocking/patching if the test module defines a ``configure_loader_modules`` fixture.
    """
    # If the test module defines a configure_loader_modules function, we'll setup the LoaderModuleMock
    # which is what actually sets up the salt loader mocking, if not, it's a no-op
    try:
        request.node.module.configure_loader_modules
    except AttributeError:
        # The test module does not define a `configure_loader_modules` function at all
        # Carry on testing
        yield
    else:
        # Mock salt's loader with what the `configure_loader_modules` fixture returns
        configure_loader_modules = request.getfixturevalue("configure_loader_modules")
        with LoaderModuleMock(configure_loader_modules) as loader_mock:
            yield loader_mock
