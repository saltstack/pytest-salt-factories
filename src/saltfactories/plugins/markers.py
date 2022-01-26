"""
Salt Factories Markers.
"""
import pytest

import saltfactories.utils.functional
import saltfactories.utils.markers


@pytest.hookimpl(trylast=True)
def pytest_runtest_setup(item):
    """
    Fixtures injection based on markers or test skips based on CLI arguments.
    """
    __tracebackhide__ = True
    saltfactories.utils.markers.evaluate_markers(item)


@pytest.mark.trylast
def pytest_configure(config):
    """
    Configure the pytest plugin.

    Called after command line options have been parsed
    and all plugins and initial conftest files been loaded.
    """
    # Expose the markers we use to pytest CLI
    config.addinivalue_line(
        "markers",
        "requires_salt_modules(*required_module_names): Skip if at least one module is not available.",
    )
    config.addinivalue_line(
        "markers",
        "requires_salt_states(*required_state_names): Skip if at least one state module is not available.",
    )


@pytest.fixture(scope="session")
def session_markers_loader(salt_factories):
    """
    Session scoped loaders fixture.
    """
    minion_id = "session-markers-minion"
    overrides = {
        "file_client": "local",
        "features": {"enable_slsvars_fixes": True},
    }
    factory = salt_factories.salt_minion_daemon(
        minion_id,
        overrides=overrides,
    )
    loader_instance = saltfactories.utils.functional.Loaders(factory.config.copy())
    # Sync Everything
    loader_instance.modules.saltutil.sync_all()
    # Reload Everything - This is required or custom modules in _modules will not be found
    loader_instance.reload_all()
    return loader_instance
