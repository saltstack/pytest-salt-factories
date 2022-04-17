import pytest


@pytest.fixture(scope="package")
def master_id():
    return "integration-cli-master"


@pytest.fixture(scope="package")
def minion_id():
    return "integration-cli-minion"


@pytest.fixture(scope="package")
def salt_master(salt_factories, master_id):
    """
    This fixture just configures and starts a salt-master.
    """
    overrides = {"open_mode": True}
    factory = salt_factories.salt_master_daemon(master_id, overrides=overrides)
    with factory.started():
        yield factory


@pytest.fixture(scope="package")
def salt_minion(salt_factories, minion_id, salt_master):
    """
    This fixture just configures and starts a salt-minion.
    """
    factory = salt_master.salt_minion_daemon(minion_id)
    with factory.started():
        yield factory


@pytest.fixture
def salt_cli(salt_master, salt_cli_timeout):
    return salt_master.salt_cli(timeout=salt_cli_timeout)
