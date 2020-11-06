import pytest

from saltfactories.utils.loader import LoaderModuleMock


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """
    Fixtures injection based on markers or test skips based on CLI arguments
    """
    try:
        fixture = item.module.configure_loader_modules
        if "_pytestfixturefunction" not in dir(fixture):
            raise RuntimeError(
                "The module {} defines a configure_loader_modules function but "
                "that function is not a fixture".format(item.module)
            )
        # If the module defines a configure_loader_modules,
        # we'll inject setup_loader_mock which is what actually
        # sets up the salt loader mocking
        item.fixturenames.append("setup_loader_mock")
    except AttributeError:
        pass


@pytest.fixture
def setup_loader_mock(configure_loader_modules):
    with LoaderModuleMock(configure_loader_modules) as loader_mock:
        yield loader_mock
