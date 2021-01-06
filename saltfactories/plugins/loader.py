import logging

import pytest

from saltfactories.utils.loader import LoaderModuleMock

log = logging.getLogger(__name__)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """
    Inject the ``setup_loader_mock`` fixture if the test module has a ``configure_loader_modules``
    fixture defined.

    ``setup_loader_mock`` is what actually takes care of patching/mocking the salt dunders prior
    to running the test.
    """
    # If the module defines a configure_loader_modules, we'll inject setup_loader_mock
    # which is what actually sets up the salt loader mocking
    try:
        fixture = item.module.configure_loader_modules
    except AttributeError:
        # The test module does not define a `configure_loader_modules` function at all
        pass
    else:
        # The test module defines a `configure_loader_modules` function. Is it a fixture?
        try:
            fixture._pytestfixturefunction
        except AttributeError:
            # It's not a fixture, raise an error
            raise RuntimeError(
                "The module {} defines a configure_loader_modules function but "
                "that function is not a fixture".format(item.module)
            )
        else:
            # It's a fixture. Inject `setup_loader_mock` as the first fixture because it needs to
            # be evaluated as soon as possible to allow other fixtures to mock/patch the salt dunders
            # prior to running the test
            if "setup_loader_mock" not in item.fixturenames:
                item.fixturenames.insert(0, "setup_loader_mock")


@pytest.fixture
def setup_loader_mock(configure_loader_modules):
    with LoaderModuleMock(configure_loader_modules) as loader_mock:
        yield loader_mock
