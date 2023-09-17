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
def salt_master(salt_factories, master_id):
    """
    This fixture just configures a salt-master. It does not start one.
    """
    return salt_factories.salt_master_daemon(master_id)


@pytest.fixture
def salt_minion(salt_master, minion_id):
    """
    This fixture just configures a salt-minion. It does not start one.
    """
    return salt_master.salt_minion_daemon(minion_id)


@pytest.fixture
def salt_proxy_minion(salt_master, proxy_minion_id):
    """
    This fixture just configures a salt-minion. It does not start one.
    """
    return salt_master.salt_proxy_minion_daemon(proxy_minion_id)


@pytest.fixture(scope="session")
def cli_salt_version(salt_version, salt_version_info, salt_version_name):
    _salt_version = f"{salt_version}"
    if salt_version_info >= (3006, 3):
        _salt_version += f" ({salt_version_name})"
    return _salt_version
