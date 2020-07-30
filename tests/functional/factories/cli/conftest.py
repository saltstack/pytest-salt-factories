"""
tests.functional.factories.cli.conftest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
import pkg_resources
import pytest


@pytest.fixture(scope="package")
def salt_version():
    return pkg_resources.get_distribution("salt").version


@pytest.fixture(scope="package")
def master_id():
    return "functional-cli-master"


@pytest.fixture(scope="package")
def minion_id():
    return "functional-cli-master"


@pytest.fixture
def salt_master_config(request, salt_factories, master_id):
    """
    This fixture just configures a salt-master. It does not start one.
    """
    return salt_factories.configure_master(request, master_id)


@pytest.fixture
def salt_minion_config(request, salt_factories, minion_id):
    """
    This fixture just configures a salt-minion. It does not start one.
    """
    return salt_factories.configure_minion(request, minion_id)
