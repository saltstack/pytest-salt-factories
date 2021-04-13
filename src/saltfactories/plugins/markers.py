import os

import pytest

import saltfactories.utils.functional
import saltfactories.utils.markers


def pytest_addoption(parser):
    """
    register argparse-style options and ini-style config values.
    """
    test_selection_group = parser.getgroup("Tests Selection")
    test_selection_group.addoption(
        "--run-destructive",
        action="store_true",
        default=False,
        help="Run destructive tests. These tests can include adding "
        "or removing users from your system for example. "
        "Default: False",
    )
    test_selection_group.addoption(
        "--run-expensive",
        action="store_true",
        default=False,
        help="Run expensive tests. These tests usually involve costs "
        "like for example bootstrapping a cloud VM. "
        "Default: False",
    )


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """
    Fixtures injection based on markers or test skips based on CLI arguments
    """
    __tracebackhide__ = True
    saltfactories.utils.markers.evaluate_markers(item)


@pytest.mark.trylast
def pytest_configure(config):
    """
    called after command line options have been parsed
    and all plugins and initial conftest files been loaded.
    """
    # Expose the markers we use to pytest CLI
    config.addinivalue_line(
        "markers",
        "destructive_test: Run destructive tests. These tests can include adding "
        "or removing users from your system for example.",
    )
    config.addinivalue_line(
        "markers",
        "expensive_test: Run expensive tests. These tests can include starting resources "
        "which cost money, like VMs, for example.",
    )
    config.addinivalue_line(
        "markers",
        "skip_if_not_root: Skip if the current user is not root on non windows platforms or not "
        "Administrator on windows platforms",
    )
    config.addinivalue_line("markers", "skip_if_not_root: Skip if the current user is not `root`.")
    config.addinivalue_line(
        "markers",
        "skip_if_binaries_missing(*binaries, check_all=True, message=None):"
        "If 'check_all' is True, all binaries must exist."
        "If 'check_all' is False, then only one the passed binaries needs to be found. Usefull when, "
        "for example, passing a list of python interpreter names(python3.5, python3, python), where "
        "only one needs to exist.",
    )
    config.addinivalue_line(
        "markers",
        "requires_network(only_local_network=False): Skip if no networking is set up. "
        "If 'only_local_network' is 'True', only the local network is checked.",
    )
    # Platform Skip Markers
    config.addinivalue_line(
        "markers",
        "skip_on_windows: Skip test on Windows",
    )
    config.addinivalue_line(
        "markers",
        "skip_unless_on_windows: Skip test unless on Windows",
    )
    config.addinivalue_line(
        "markers",
        "skip_on_linux: Skip test on Linux",
    )
    config.addinivalue_line(
        "markers",
        "skip_unless_on_linux: Skip test unless on Linux",
    )
    config.addinivalue_line(
        "markers",
        "skip_on_darwin: Skip test on Darwin",
    )
    config.addinivalue_line(
        "markers",
        "skip_unless_on_darwin: Skip test unless on Darwin",
    )
    config.addinivalue_line(
        "markers",
        "skip_on_sunos: Skip test on SunOS",
    )
    config.addinivalue_line(
        "markers",
        "skip_unless_on_sunos: Skip test unless on SunOS",
    )
    config.addinivalue_line(
        "markers",
        "skip_on_smartos: Skip test on SmartOS",
    )
    config.addinivalue_line(
        "markers",
        "skip_unless_on_smartos: Skip test unless on SmartOS",
    )
    config.addinivalue_line(
        "markers",
        "skip_on_freebsd: Skip test on FreeBSD",
    )
    config.addinivalue_line(
        "markers",
        "skip_unless_on_freebsd: Skip test unless on FreeBSD",
    )
    config.addinivalue_line(
        "markers",
        "skip_on_netbsd: Skip test on NetBSD",
    )
    config.addinivalue_line(
        "markers",
        "skip_unless_on_netbsd: Skip test unless on NetBSD",
    )
    config.addinivalue_line(
        "markers",
        "skip_on_openbsd: Skip test on OpenBSD",
    )
    config.addinivalue_line(
        "markers",
        "skip_unless_on_openbsd: Skip test unless on OpenBSD",
    )
    config.addinivalue_line(
        "markers",
        "skip_on_aix: Skip test on AIX",
    )
    config.addinivalue_line(
        "markers",
        "skip_unless_on_aix: Skip test unless on AIX",
    )
    config.addinivalue_line(
        "markers",
        "skip_on_aarch64: Skip test on AArch64",
    )
    config.addinivalue_line(
        "markers",
        "skip_unless_on_aarch64: Skip test unless on AArch64",
    )
    config.addinivalue_line(
        "markers",
        "skip_on_platforms(windows=False, linux=False, darwin=False, sunos=False, smartos=False, freebsd=False, "
        "netbsd=False, openbsd=False, aix=False, aarch64=False): Pass True to one or more platform names to get the test skipped "
        "on those platforms",
    )
    config.addinivalue_line(
        "markers",
        "skip_unless_on_platforms(windows=False, linux=False, darwin=False, sunos=False, smartos=False, freebsd=False, "
        "netbsd=False, openbsd=False, aix=False, aarch64=False): Pass True to one or more platform names to get the test skipped "
        "unless the chosen platforms match",
    )
    config.addinivalue_line(
        "markers",
        "requires_salt_modules(*required_module_names): Skip if at least one module is not available.",
    )
    config.addinivalue_line(
        "markers",
        "requires_salt_states(*required_state_names): Skip if at least one state module is not available.",
    )

    # Add keys to environ in order to support Salt's helper decorators while it does not migrate to pytest markers
    env2cli = (("DESTRUCTIVE_TESTS", "--run-destructive"), ("EXPENSIVE_TESTS", "--run-expensive"))
    for envkey, cliflag in env2cli:
        os.environ[str(envkey)] = str(config.getoption(cliflag)).lower()


@pytest.fixture(scope="session")
def session_markers_loader(salt_factories):
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
