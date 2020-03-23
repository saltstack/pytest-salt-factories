# -*- coding: utf-8 -*-
"""
    saltfactories.plugins.markers
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Salt Factories Related Markers
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import pytest
import six

import saltfactories.utils.markers
import saltfactories.utils.platform


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
    destructive_tests_marker = item.get_closest_marker("destructive_test")
    if destructive_tests_marker is not None:
        if item.config.getoption("--run-destructive") is False:
            item._skipped_by_mark = True
            pytest.skip("Destructive tests are disabled")

    expensive_tests_marker = item.get_closest_marker("expensive_test")
    if expensive_tests_marker is not None:
        if item.config.getoption("--run-expensive") is False:
            item._skipped_by_mark = True
            pytest.skip("Expensive tests are disabled")

    skip_if_not_root_marker = item.get_closest_marker("skip_if_not_root")
    if skip_if_not_root_marker is not None:
        skip_reason = saltfactories.utils.markers.skip_if_not_root()
        if skip_reason:
            item._skipped_by_mark = True
            pytest.skip(skip_reason)

    skip_if_binaries_missing_marker = item.get_closest_marker("skip_if_binaries_missing")
    if skip_if_binaries_missing_marker is not None:
        binaries = skip_if_binaries_missing_marker.args
        if len(binaries) == 1 and not isinstance(binaries[0], six.string_types):
            raise RuntimeError(
                "Do not pass a list as binaries to the skip_if_binaries_missing() marker. "
                "Instead, pass each binary as an argument to skip_if_binaries_missing()."
            )
        skip_reason = saltfactories.utils.markers.skip_if_binaries_missing(
            binaries, **skip_if_binaries_missing_marker.kwargs
        )
        if skip_reason:
            item._skipped_by_mark = True
            pytest.skip(skip_reason)

    requires_network_marker = item.get_closest_marker("requires_network")
    if requires_network_marker is not None:
        only_local_network = requires_network_marker.kwargs.get("only_local_network", False)
        local_skip_reason = saltfactories.utils.markers.skip_if_no_local_network()
        if local_skip_reason:
            # Since we're only supposed to check local network, and no
            # local network was detected, skip the test
            item._skipped_by_mark = True
            pytest.skip(local_skip_reason)

        if only_local_network is False:
            remote_skip_reason = saltfactories.utils.markers.skip_if_no_remote_network()
            if remote_skip_reason:
                item._skipped_by_mark = True
                pytest.skip(remote_skip_reason)

    # Platform Skip Markers
    skip_on_windows_marker = item.get_closest_marker("skip_on_windows")
    if skip_on_windows_marker is not None:
        if saltfactories.utils.platform.is_windows():
            item._skipped_by_mark = True
            pytest.skip("Skipped on Windows")

    skip_on_linux_marker = item.get_closest_marker("skip_on_linux")
    if skip_on_linux_marker is not None:
        if saltfactories.utils.platform.is_linux():
            item._skipped_by_mark = True
            pytest.skip("Skipped on Linux")

    skip_on_darwin_marker = item.get_closest_marker("skip_on_darwin")
    if skip_on_darwin_marker is not None:
        if saltfactories.utils.platform.is_darwin():
            item._skipped_by_mark = True
            pytest.skip("Skipped on Darwin")

    skip_on_sunos_marker = item.get_closest_marker("skip_on_sunos")
    if skip_on_sunos_marker is not None:
        if saltfactories.utils.platform.is_sunos():
            item._skipped_by_mark = True
            pytest.skip("Skipped on SunOS")

    skip_on_smartos_marker = item.get_closest_marker("skip_on_smartos")
    if skip_on_smartos_marker is not None:
        if saltfactories.utils.platform.is_smartos():
            item._skipped_by_mark = True
            pytest.skip("Skipped on SmartOS")

    skip_on_freebsd_marker = item.get_closest_marker("skip_on_freebsd")
    if skip_on_freebsd_marker is not None:
        if saltfactories.utils.platform.is_freebsd():
            item._skipped_by_mark = True
            pytest.skip("Skipped on FreeBSD")

    skip_on_netbsd_marker = item.get_closest_marker("skip_on_netbsd")
    if skip_on_netbsd_marker is not None:
        if saltfactories.utils.platform.is_netbsd():
            item._skipped_by_mark = True
            pytest.skip("Skipped on NetBSD")

    skip_on_openbsd_marker = item.get_closest_marker("skip_on_openbsd")
    if skip_on_openbsd_marker is not None:
        if saltfactories.utils.platform.is_openbsd():
            item._skipped_by_mark = True
            pytest.skip("Skipped on OpenBSD")

    skip_on_aix_marker = item.get_closest_marker("skip_on_aix")
    if skip_on_aix_marker is not None:
        if saltfactories.utils.platform.is_aix():
            item._skipped_by_mark = True
            pytest.skip("Skipped on AIX")


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
        "markers", "skip_on_windows: Skip test on Windows",
    )
    config.addinivalue_line(
        "markers", "skip_on_linux: Skip test on Linux",
    )
    config.addinivalue_line(
        "markers", "skip_on_darwin: Skip test on Darwin",
    )
    config.addinivalue_line(
        "markers", "skip_on_sunos: Skip test on SunOS",
    )
    config.addinivalue_line(
        "markers", "skip_on_smartos: Skip test on SmartOS",
    )
    config.addinivalue_line(
        "markers", "skip_on_freebsd: Skip test on FreeBSD",
    )
    config.addinivalue_line(
        "markers", "skip_on_netbsd: Skip test on NetBSD",
    )
    config.addinivalue_line(
        "markers", "skip_on_openbsd: Skip test on OpenBSD",
    )
    config.addinivalue_line(
        "markers", "skip_on_aix: Skip test on AIX",
    )
