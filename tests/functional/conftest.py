import pytest


@pytest.fixture(scope="package", autouse=True)
def skip_on_system_install_tests(salt_factories):
    if salt_factories.system_install:
        pytest.skip("Test should not run against system install")
