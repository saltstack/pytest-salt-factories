"""
tests.functional.factories.cli.conftest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
import pytest

from saltfactories.factories.daemons.master import SaltMasterFactory
from saltfactories.factories.daemons.minion import SaltMinionFactory
from saltfactories.factories.daemons.proxy import SaltProxyMinionFactory


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
    config = salt_factories.configure_salt_master(request, master_id)
    return SaltMasterFactory(
        config=config, cli_script_name="salt-master", factories_manager=salt_factories
    )


@pytest.fixture
def salt_minion(request, salt_factories, minion_id, salt_master):
    """
    This fixture just configures a salt-minion. It does not start one.
    """
    config = salt_master.configure_salt_minion(request, minion_id)
    return SaltMinionFactory(
        config=config, cli_script_name="salt-minion", factories_manager=salt_factories
    )


@pytest.fixture
def salt_proxy_minion(request, salt_factories, salt_master, proxy_minion_id):
    """
    This fixture just configures a salt-minion. It does not start one.
    """
    config = salt_factories.configure_salt_proxy_minion(
        request, proxy_minion_id, master_id=salt_master.id
    )
    return SaltProxyMinionFactory(
        config=config, cli_script_name="salt-proxy", factories_manager=salt_factories
    )
