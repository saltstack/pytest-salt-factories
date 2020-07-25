"""
    saltfactories.plugins.markers
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Salt Factories Related Markers
"""
import os

import pytest

import saltfactories.utils.compat
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
    if destructive_tests_marker is not None or saltfactories.utils.compat.has_unittest_attr(
        item, "__destructive_test__"
    ):
        if item.config.getoption("--run-destructive") is False:
            item._skipped_by_mark = True
            pytest.skip("Destructive tests are disabled")

    expensive_tests_marker = item.get_closest_marker("expensive_test")
    if expensive_tests_marker is not None or saltfactories.utils.compat.has_unittest_attr(
        item, "__expensive_test__"
    ):
        if item.config.getoption("--run-expensive") is False:
            item._skipped_by_mark = True
            pytest.skip("Expensive tests are disabled")

    skip_if_not_root_marker = item.get_closest_marker("skip_if_not_root")
    if skip_if_not_root_marker is not None or saltfactories.utils.compat.has_unittest_attr(
        item, "__skip_if_not_root__"
    ):
        skip_reason = saltfactories.utils.markers.skip_if_not_root()
        if skip_reason:
            item._skipped_by_mark = True
            pytest.skip(skip_reason)

    skip_if_binaries_missing_marker = item.get_closest_marker("skip_if_binaries_missing")
    if skip_if_binaries_missing_marker is not None or saltfactories.utils.compat.has_unittest_attr(
        item, "__skip_if_binaries_missing__"
    ):
        binaries = skip_if_binaries_missing_marker.args
        if len(binaries) == 1 and not isinstance(binaries[0], str):
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
    if requires_network_marker is not None or saltfactories.utils.compat.has_unittest_attr(
        item, "__requires_network__"
    ):
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
        if skip_on_windows_marker.args:
            raise RuntimeError("The skip_on_windows marker does not accept any arguments")
        reason = skip_on_windows_marker.kwargs.pop("reason", None)
        if skip_on_windows_marker.kwargs:
            raise RuntimeError(
                "The skip_on_windows marker only accepts 'reason' as a keyword argument."
            )
        if reason is None:
            reason = "Skipped on Windows"
        if saltfactories.utils.platform.is_windows():
            item._skipped_by_mark = True
            pytest.skip(reason)

    skip_unless_on_windows_marker = item.get_closest_marker("skip_unless_on_windows")
    if skip_unless_on_windows_marker is not None:
        if skip_unless_on_windows_marker.args:
            raise RuntimeError("The skip_unless_on_windows marker does not accept any arguments")
        reason = skip_unless_on_windows_marker.kwargs.pop("reason", None)
        if skip_unless_on_windows_marker.kwargs:
            raise RuntimeError(
                "The skip_unless_on_windows marker only accepts 'reason' as a keyword argument."
            )
        if reason is None:
            reason = "Platform is not Windows, skipped"
        if not saltfactories.utils.platform.is_windows():
            item._skipped_by_mark = True
            pytest.skip(reason)

    skip_on_linux_marker = item.get_closest_marker("skip_on_linux")
    if skip_on_linux_marker is not None:
        if skip_on_linux_marker.args:
            raise RuntimeError("The skip_on_linux marker does not accept any arguments")
        reason = skip_on_linux_marker.kwargs.pop("reason", None)
        if skip_on_linux_marker.kwargs:
            raise RuntimeError(
                "The skip_on_linux marker only accepts 'reason' as a keyword argument."
            )
        if reason is None:
            reason = "Skipped on Linux"
        if saltfactories.utils.platform.is_linux():
            item._skipped_by_mark = True
            pytest.skip(reason)

    skip_unless_on_linux_marker = item.get_closest_marker("skip_unless_on_linux")
    if skip_unless_on_linux_marker is not None:
        if skip_unless_on_linux_marker.args:
            raise RuntimeError("The skip_unless_on_linux marker does not accept any arguments")
        reason = skip_unless_on_linux_marker.kwargs.pop("reason", None)
        if skip_unless_on_linux_marker.kwargs:
            raise RuntimeError(
                "The skip_unless_on_linux marker only accepts 'reason' as a keyword argument."
            )
        if reason is None:
            reason = "Platform is not Linux, skipped"
        if not saltfactories.utils.platform.is_linux():
            item._skipped_by_mark = True
            pytest.skip(reason)

    skip_on_darwin_marker = item.get_closest_marker("skip_on_darwin")
    if skip_on_darwin_marker is not None:
        if skip_on_darwin_marker.args:
            raise RuntimeError("The skip_on_darwin marker does not accept any arguments")
        reason = skip_on_darwin_marker.kwargs.pop("reason", None)
        if skip_on_darwin_marker.kwargs:
            raise RuntimeError(
                "The skip_on_darwin marker only accepts 'reason' as a keyword argument."
            )
        if reason is None:
            reason = "Skipped on Darwin"
        if saltfactories.utils.platform.is_darwin():
            item._skipped_by_mark = True
            pytest.skip(reason)

    skip_unless_on_darwin_marker = item.get_closest_marker("skip_unless_on_darwin")
    if skip_unless_on_darwin_marker is not None:
        if skip_unless_on_darwin_marker.args:
            raise RuntimeError("The skip_unless_on_darwin marker does not accept any arguments")
        reason = skip_unless_on_darwin_marker.kwargs.pop("reason", None)
        if skip_unless_on_darwin_marker.kwargs:
            raise RuntimeError(
                "The skip_unless_on_darwin marker only accepts 'reason' as a keyword argument."
            )
        if reason is None:
            reason = "Platform is not Darwin, skipped"
        if not saltfactories.utils.platform.is_darwin():
            item._skipped_by_mark = True
            pytest.skip(reason)

    skip_on_sunos_marker = item.get_closest_marker("skip_on_sunos")
    if skip_on_sunos_marker is not None:
        if skip_on_sunos_marker.args:
            raise RuntimeError("The skip_on_sunos marker does not accept any arguments")
        reason = skip_on_sunos_marker.kwargs.pop("reason", None)
        if skip_on_sunos_marker.kwargs:
            raise RuntimeError(
                "The skip_on_sunos marker only accepts 'reason' as a keyword argument."
            )
        if reason is None:
            reason = "Skipped on SunOS"
        if saltfactories.utils.platform.is_sunos():
            item._skipped_by_mark = True
            pytest.skip(reason)

    skip_unless_on_sunos_marker = item.get_closest_marker("skip_unless_on_sunos")
    if skip_unless_on_sunos_marker is not None:
        if skip_unless_on_sunos_marker.args:
            raise RuntimeError("The skip_unless_on_sunos marker does not accept any arguments")
        reason = skip_unless_on_sunos_marker.kwargs.pop("reason", None)
        if skip_unless_on_sunos_marker.kwargs:
            raise RuntimeError(
                "The skip_unless_on_sunos marker only accepts 'reason' as a keyword argument."
            )
        if reason is None:
            reason = "Platform is not SunOS, skipped"
        if not saltfactories.utils.platform.is_sunos():
            item._skipped_by_mark = True
            pytest.skip(reason)

    skip_on_smartos_marker = item.get_closest_marker("skip_on_smartos")
    if skip_on_smartos_marker is not None:
        if skip_on_smartos_marker.args:
            raise RuntimeError("The skip_on_smartos marker does not accept any arguments")
        reason = skip_on_smartos_marker.kwargs.pop("reason", None)
        if skip_on_smartos_marker.kwargs:
            raise RuntimeError(
                "The skip_on_smartos marker only accepts 'reason' as a keyword argument."
            )
        if reason is None:
            reason = "Skipped on SmartOS"
        if saltfactories.utils.platform.is_smartos():
            item._skipped_by_mark = True
            pytest.skip(reason)

    skip_unless_on_smartos_marker = item.get_closest_marker("skip_unless_on_smartos")
    if skip_unless_on_smartos_marker is not None:
        if skip_unless_on_smartos_marker.args:
            raise RuntimeError("The skip_unless_on_smartos marker does not accept any arguments")
        reason = skip_unless_on_smartos_marker.kwargs.pop("reason", None)
        if skip_unless_on_smartos_marker.kwargs:
            raise RuntimeError(
                "The skip_unless_on_smartos marker only accepts 'reason' as a keyword argument."
            )
        if reason is None:
            reason = "Platform is not SmartOS, skipped"
        if not saltfactories.utils.platform.is_smartos():
            item._skipped_by_mark = True
            pytest.skip(reason)

    skip_on_freebsd_marker = item.get_closest_marker("skip_on_freebsd")
    if skip_on_freebsd_marker is not None:
        if skip_on_freebsd_marker.args:
            raise RuntimeError("The skip_on_freebsd marker does not accept any arguments")
        reason = skip_on_freebsd_marker.kwargs.pop("reason", None)
        if skip_on_freebsd_marker.kwargs:
            raise RuntimeError(
                "The skip_on_freebsd marker only accepts 'reason' as a keyword argument."
            )
        if reason is None:
            reason = "Skipped on FreeBSD"
        if saltfactories.utils.platform.is_freebsd():
            item._skipped_by_mark = True
            pytest.skip(reason)

    skip_unless_on_freebsd_marker = item.get_closest_marker("skip_unless_on_freebsd")
    if skip_unless_on_freebsd_marker is not None:
        if skip_unless_on_freebsd_marker.args:
            raise RuntimeError("The skip_unless_on_freebsd marker does not accept any arguments")
        reason = skip_unless_on_freebsd_marker.kwargs.pop("reason", None)
        if skip_unless_on_freebsd_marker.kwargs:
            raise RuntimeError(
                "The skip_unless_on_freebsd marker only accepts 'reason' as a keyword argument."
            )
        if reason is None:
            reason = "Platform is not FreeBSD, skipped"
        if not saltfactories.utils.platform.is_freebsd():
            item._skipped_by_mark = True
            pytest.skip(reason)

    skip_on_netbsd_marker = item.get_closest_marker("skip_on_netbsd")
    if skip_on_netbsd_marker is not None:
        if skip_on_netbsd_marker.args:
            raise RuntimeError("The skip_on_netbsd marker does not accept any arguments")
        reason = skip_on_netbsd_marker.kwargs.pop("reason", None)
        if skip_on_netbsd_marker.kwargs:
            raise RuntimeError(
                "The skip_on_netbsd marker only accepts 'reason' as a keyword argument."
            )
        if reason is None:
            reason = "Skipped on NetBSD"
        if saltfactories.utils.platform.is_netbsd():
            item._skipped_by_mark = True
            pytest.skip(reason)

    skip_unless_on_netbsd_marker = item.get_closest_marker("skip_unless_on_netbsd")
    if skip_unless_on_netbsd_marker is not None:
        if skip_unless_on_netbsd_marker.args:
            raise RuntimeError("The skip_unless_on_netbsd marker does not accept any arguments")
        reason = skip_unless_on_netbsd_marker.kwargs.pop("reason", None)
        if skip_unless_on_netbsd_marker.kwargs:
            raise RuntimeError(
                "The skip_unless_on_netbsd marker only accepts 'reason' as a keyword argument."
            )
        if reason is None:
            reason = "Platform is not NetBSD, skipped"
        if not saltfactories.utils.platform.is_netbsd():
            item._skipped_by_mark = True
            pytest.skip(reason)

    skip_on_openbsd_marker = item.get_closest_marker("skip_on_openbsd")
    if skip_on_openbsd_marker is not None:
        if skip_on_openbsd_marker.args:
            raise RuntimeError("The skip_on_openbsd marker does not accept any arguments")
        reason = skip_on_openbsd_marker.kwargs.pop("reason", None)
        if skip_on_openbsd_marker.kwargs:
            raise RuntimeError(
                "The skip_on_openbsd marker only accepts 'reason' as a keyword argument."
            )
        if reason is None:
            reason = "Skipped on OpenBSD"
        if saltfactories.utils.platform.is_openbsd():
            item._skipped_by_mark = True
            pytest.skip(reason)

    skip_unless_on_openbsd_marker = item.get_closest_marker("skip_unless_on_openbsd")
    if skip_unless_on_openbsd_marker is not None:
        if skip_unless_on_openbsd_marker.args:
            raise RuntimeError("The skip_unless_on_openbsd marker does not accept any arguments")
        reason = skip_unless_on_openbsd_marker.kwargs.pop("reason", None)
        if skip_unless_on_openbsd_marker.kwargs:
            raise RuntimeError(
                "The skip_unless_on_openbsd marker only accepts 'reason' as a keyword argument."
            )
        if reason is None:
            reason = "Platform is not OpenBSD, skipped"
        if not saltfactories.utils.platform.is_openbsd():
            item._skipped_by_mark = True
            pytest.skip(reason)

    skip_on_aix_marker = item.get_closest_marker("skip_on_aix")
    if skip_on_aix_marker is not None:
        if skip_on_aix_marker.args:
            raise RuntimeError("The skip_on_aix marker does not accept any arguments")
        reason = skip_on_aix_marker.kwargs.pop("reason", None)
        if skip_on_aix_marker.kwargs:
            raise RuntimeError(
                "The skip_on_aix marker only accepts 'reason' as a keyword argument."
            )
        if reason is None:
            reason = "Skipped on AIX"
        if saltfactories.utils.platform.is_aix():
            item._skipped_by_mark = True
            pytest.skip(reason)

    skip_unless_on_aix_marker = item.get_closest_marker("skip_unless_on_aix")
    if skip_unless_on_aix_marker is not None:
        if skip_unless_on_aix_marker.args:
            raise RuntimeError("The skip_unless_on_aix marker does not accept any arguments")
        reason = skip_unless_on_aix_marker.kwargs.pop("reason", None)
        if skip_unless_on_aix_marker.kwargs:
            raise RuntimeError(
                "The skip_unless_on_aix marker only accepts 'reason' as a keyword argument."
            )
        if reason is None:
            reason = "Platform is not AIX, skipped"
        if not saltfactories.utils.platform.is_aix():
            item._skipped_by_mark = True
            pytest.skip(reason)

    skip_on_platforms_marker = item.get_closest_marker("skip_on_platforms")
    if skip_on_platforms_marker is not None:
        if skip_on_platforms_marker.args:
            raise RuntimeError("The skip_on_platforms marker does not accept any arguments")
        reason = skip_on_platforms_marker.kwargs.pop("reason", None)
        if not skip_on_platforms_marker.kwargs:
            raise RuntimeError(
                "Pass at least one platform to skip_on_platforms as a keyword argument"
            )
        if not any(skip_on_platforms_marker.kwargs.values()):
            raise RuntimeError(
                "Pass at least one platform with a True value to skip_on_platforms as a keyword argument"
            )
        if reason is None:
            reason = "Skipped on platform match"
        try:
            if saltfactories.utils.platform.on_platforms(**skip_on_platforms_marker.kwargs):
                item._skipped_by_mark = True
                pytest.skip(reason)
        except TypeError as exc:
            raise RuntimeError("Passed an invalid platform to skip_on_platforms: {}".format(exc))

    skip_unless_on_platforms_marker = item.get_closest_marker("skip_unless_on_platforms")
    if skip_unless_on_platforms_marker is not None:
        if skip_unless_on_platforms_marker.args:
            raise RuntimeError("The skip_unless_on_platforms marker does not accept any arguments")
        reason = skip_unless_on_platforms_marker.kwargs.pop("reason", None)
        if not skip_unless_on_platforms_marker.kwargs:
            raise RuntimeError(
                "Pass at least one platform to skip_unless_on_platforms as a keyword argument"
            )
        if not any(skip_unless_on_platforms_marker.kwargs.values()):
            raise RuntimeError(
                "Pass at least one platform with a True value to skip_unless_on_platforms as a keyword argument"
            )
        if reason is None:
            reason = "Platform(s) do not match, skipped"
        try:
            if not saltfactories.utils.platform.on_platforms(
                **skip_unless_on_platforms_marker.kwargs
            ):
                item._skipped_by_mark = True
                pytest.skip(reason)
        except TypeError as exc:
            raise RuntimeError(
                "Passed an invalid platform to skip_unless_on_platforms: {}".format(exc)
            )


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
        "markers", "skip_unless_on_windows: Skip test unless on Windows",
    )
    config.addinivalue_line(
        "markers", "skip_on_linux: Skip test on Linux",
    )
    config.addinivalue_line(
        "markers", "skip_unless_on_linux: Skip test unless on Linux",
    )
    config.addinivalue_line(
        "markers", "skip_on_darwin: Skip test on Darwin",
    )
    config.addinivalue_line(
        "markers", "skip_unless_on_darwin: Skip test unless on Darwin",
    )
    config.addinivalue_line(
        "markers", "skip_on_sunos: Skip test on SunOS",
    )
    config.addinivalue_line(
        "markers", "skip_unless_on_sunos: Skip test unless on SunOS",
    )
    config.addinivalue_line(
        "markers", "skip_on_smartos: Skip test on SmartOS",
    )
    config.addinivalue_line(
        "markers", "skip_unless_on_smartos: Skip test unless on SmartOS",
    )
    config.addinivalue_line(
        "markers", "skip_on_freebsd: Skip test on FreeBSD",
    )
    config.addinivalue_line(
        "markers", "skip_unless_on_freebsd: Skip test unless on FreeBSD",
    )
    config.addinivalue_line(
        "markers", "skip_on_netbsd: Skip test on NetBSD",
    )
    config.addinivalue_line(
        "markers", "skip_unless_on_netbsd: Skip test unless on NetBSD",
    )
    config.addinivalue_line(
        "markers", "skip_on_openbsd: Skip test on OpenBSD",
    )
    config.addinivalue_line(
        "markers", "skip_unless_on_openbsd: Skip test unless on OpenBSD",
    )
    config.addinivalue_line(
        "markers", "skip_on_aix: Skip test on AIX",
    )
    config.addinivalue_line(
        "markers", "skip_unless_on_aix: Skip test unless on AIX",
    )
    config.addinivalue_line(
        "markers",
        "skip_on_platforms(windows=False, linux=False, darwin=False, sunos=False, smartos=False, freebsd=False, "
        "netbsd=False, openbsd=False, aix=False): Pass True to one or more platform names to get the test skipped "
        "on those platforms",
    )
    config.addinivalue_line(
        "markers",
        "skip_unless_on_platforms(windows=False, linux=False, darwin=False, sunos=False, smartos=False, freebsd=False, "
        "netbsd=False, openbsd=False, aix=False): Pass True to one or more platform names to get the test skipped "
        "unless the chosen platforms match",
    )

    # Add keys to environ in order to support Salt's helper decorators while it does not migrate to pytest markers
    env2cli = (("DESTRUCTIVE_TESTS", "--run-destructive"), ("EXPENSIVE_TESTS", "--run-expensive"))
    for envkey, cliflag in env2cli:
        os.environ[str(envkey)] = str(config.getoption(cliflag)).lower()
