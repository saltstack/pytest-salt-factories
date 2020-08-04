"""
saltfactories.hookspec
~~~~~~~~~~~~~~~~~~~~~~

Salt Factories Hooks
"""
import pytest


@pytest.hookspec(firstresult=True)
def pytest_saltfactories_handle_key_auth_event(
    factories_manager, master_id, minion_id, keystate, payload
):
    """
    This hook is called for every auth event on the masters
    """
