"""
tests.functional.factories.cli.conftest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
import pytest


@pytest.fixture(scope="package")
def master_id():
    return "functional-cli-master"


@pytest.fixture(scope="package")
def minion_id():
    return "functional-cli-minion"


@pytest.fixture(scope="package")
def proxy_minion_id():
    return "functional-cli-proxy-minion"


@pytest.fixture
def salt_master(request, salt_factories, master_id):
    """
    This fixture just configures a salt-master. It does not start one.
    """
    return salt_factories.get_salt_master_daemon(master_id)


@pytest.fixture
def salt_minion(request, salt_factories, minion_id, salt_master):
    """
    This fixture just configures a salt-minion. It does not start one.
    """
    return salt_master.get_salt_minion_daemon(minion_id)


@pytest.fixture
def salt_proxy_minion(request, salt_factories, salt_master, proxy_minion_id):
    """
    This fixture just configures a salt-minion. It does not start one.
    """
    return salt_master.get_salt_proxy_minion_daemon(proxy_minion_id)
