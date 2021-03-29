"""
..
    PYTEST_DONT_REWRITE


saltfactories.utils.markers
~~~~~~~~~~~~~~~~~~~~~~~~~~~

PyTest Markers related utilities
"""
import contextlib
import fnmatch
import logging
import os
import sys

import pytest
import salt.utils.path
import salt.utils.win_functions

import saltfactories.utils.platform
import saltfactories.utils.ports as ports
import saltfactories.utils.socket as socket

log = logging.getLogger(__name__)


def skip_if_not_root():
    """
    Helper function to check for root/Administrator privileges

    Returns:
        str: The reason of the skip
    """
    if not sys.platform.startswith("win"):
        if os.getuid() != 0:
            return "You must be logged in as root to run this test"
    else:
        current_user = salt.utils.win_functions.get_current_user()
        if current_user != "SYSTEM":
            if not salt.utils.win_functions.is_admin(current_user):
                return "You must be logged in as an Administrator to run this test"


def skip_if_binaries_missing(binaries, check_all=True, reason=None):
    """
    Helper function to check for existing binaries

    Args:
        binaries (list or tuple):
            Iterator of binaries to check
        check_all (bool):
            If ``check_all`` is ``True``, the default, all binaries must exist.
            If ``check_all`` is ``False``, then only one the passed binaries needs to be found.
            Useful when, for example, passing a list of python interpreter names(python3.5,
            python3, python), where only one needs to exist.
        reason (str):
            The skip reason.

    Returns:
        str: The reason for the skip.
        None: Should not be skipped.
    """
    if check_all is False:
        # We only need one of the passed binaries to exist
        if salt.utils.path.which_bin(binaries) is None:
            if reason is not None:
                return reason
            return "None of the following binaries was found: {}".format(", ".join(binaries))
    else:
        for binary in binaries:
            if salt.utils.path.which(binary) is None:
                if reason is not None:
                    return reason
                return "The '{}' binary was not found".format(binary)
    log.debug("All binaries found. Searched for: %s", ", ".join(binaries))


def skip_if_no_local_network():
    """
    Helper function to check for existing local network

    Returns:
        str: The reason for the skip.
        None: Should not be skipped.
    """
    check_port = ports.get_unused_localhost_port()
    has_local_network = False
    try:
        with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as pubsock:
            pubsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            pubsock.bind(("", check_port))
        has_local_network = True
    except OSError:
        # I wonder if we just have IPV6 support?
        try:
            with contextlib.closing(socket.socket(socket.AF_INET6, socket.SOCK_STREAM)) as pubsock:
                pubsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                pubsock.bind(("", check_port))
            has_local_network = True
        except OSError:
            # Let's continue
            pass
    if has_local_network is False:
        return "No local network was detected"


def skip_if_no_remote_network():
    """
    Helper function to check for existing remote network(internet)

    Returns:
        str: The reason for the skip.
        None: Should not be skipped.
    """

    # We are using the google.com DNS records as numerical IPs to avoid
    # DNS look ups which could greatly slow down this check
    has_remote_network = False
    for addr in (
        "172.217.17.14",
        "172.217.16.238",
        "173.194.41.198",
        "173.194.41.199",
        "173.194.41.200",
        "173.194.41.201",
        "173.194.41.206",
        "173.194.41.192",
        "173.194.41.193",
        "173.194.41.194",
        "173.194.41.195",
        "173.194.41.196",
        "173.194.41.197",
        "216.58.201.174",
    ):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.25)
            sock.connect((addr, 80))
            sock.close()
            # We connected? Stop the loop
            has_remote_network = True
            break
        except OSError:
            # Let's check the next IP
            continue

    if has_remote_network is False:
        return "No internet network connection was detected"


def check_required_loader_attributes(loader_instance, loader_attr, required_items):
    """
    :type loader_instance: ~saltfactories.utils.functional.Loaders
    :param loader_instance:
        An instance of :py:class:`~saltfactories.utils.functional.Loaders`
    :param str loader_attr:
        The name of the minion attribute to check, such as 'modules' or 'states'
    :param tuple required_items:
        The items that must be part of the loader attribute for the decorated test
    :return: The modules that are not available
    :rtype: set

    """
    required_salt_items = set(required_items)
    available_items = list(getattr(loader_instance, loader_attr))
    not_available_items = set()

    name = "__not_available_{items}s__".format(items=loader_attr)
    if not hasattr(loader_instance, name):
        cached_not_available_items = set()
        setattr(loader_instance, name, cached_not_available_items)
        loader_instance._reload_all_funcs.append(cached_not_available_items.clear)
    else:
        cached_not_available_items = getattr(loader_instance, name)

    for not_available_item in cached_not_available_items:
        if not_available_item in required_salt_items:
            not_available_items.add(not_available_item)
            required_salt_items.remove(not_available_item)

    for required_item_name in required_salt_items:
        search_name = required_item_name
        if "." not in search_name:
            search_name += ".*"
        if not fnmatch.filter(available_items, search_name):
            not_available_items.add(required_item_name)
            cached_not_available_items.add(required_item_name)

    return not_available_items


def evaluate_markers(item):
    """
    Fixtures injection based on markers or test skips based on CLI arguments
    """
    destructive_tests_marker = item.get_closest_marker("destructive_test")
    if destructive_tests_marker is not None:
        if destructive_tests_marker.args or destructive_tests_marker.kwargs:
            raise pytest.UsageError(
                "The 'destructive_test' marker does not accept any arguments or keyword arguments"
            )
        if item.config.getoption("--run-destructive") is False:
            item._skipped_by_mark = True
            pytest.skip("Destructive tests are disabled")

    expensive_tests_marker = item.get_closest_marker("expensive_test")
    if expensive_tests_marker is not None:
        if expensive_tests_marker.args or expensive_tests_marker.kwargs:
            raise pytest.UsageError(
                "The 'expensive_test' marker does not accept any arguments or keyword arguments"
            )
        if item.config.getoption("--run-expensive") is False:
            item._skipped_by_mark = True
            pytest.skip("Expensive tests are disabled")

    skip_if_not_root_marker = item.get_closest_marker("skip_if_not_root")
    if skip_if_not_root_marker is not None:
        if skip_if_not_root_marker.args or skip_if_not_root_marker.kwargs:
            raise pytest.UsageError(
                "The 'skip_if_not_root' marker does not accept any arguments or keyword arguments"
            )
        skip_reason = skip_if_not_root()
        if skip_reason:
            item._skipped_by_mark = True
            pytest.skip(skip_reason)

    skip_if_binaries_missing_marker = item.get_closest_marker("skip_if_binaries_missing")
    if skip_if_binaries_missing_marker is not None:
        binaries = skip_if_binaries_missing_marker.args
        if not binaries:
            raise pytest.UsageError(
                "The 'skip_if_binaries_missing' marker needs at least one binary name to be passed"
            )
        for arg in binaries:
            if not isinstance(arg, str):
                raise pytest.UsageError(
                    "The 'skip_if_binaries_missing' marker only accepts strings as arguments. If you are "
                    "trying to pass multiple binaries, each binary should be an separate argument."
                )
        message = skip_if_binaries_missing_marker.kwargs.pop("message", None)
        if message:
            item.warn(
                """Please stop passing 'message="{0}"' and instead pass 'reason="{0}"'""".format(
                    message
                )
            )
            skip_if_binaries_missing_marker.kwargs["reason"] = message
        skip_reason = skip_if_binaries_missing(binaries, **skip_if_binaries_missing_marker.kwargs)
        if skip_reason:
            item._skipped_by_mark = True
            pytest.skip(skip_reason)

    requires_network_marker = item.get_closest_marker("requires_network")
    if requires_network_marker is not None:
        only_local_network = requires_network_marker.kwargs.get("only_local_network", False)
        local_skip_reason = skip_if_no_local_network()
        if local_skip_reason:
            # Since we're only supposed to check local network, and no
            # local network was detected, skip the test
            item._skipped_by_mark = True
            pytest.skip(local_skip_reason)

        if only_local_network is False:
            remote_skip_reason = skip_if_no_remote_network()
            if remote_skip_reason:
                item._skipped_by_mark = True
                pytest.skip(remote_skip_reason)

    # Platform Skip Markers
    skip_on_windows_marker = item.get_closest_marker("skip_on_windows")
    if skip_on_windows_marker is not None:
        if skip_on_windows_marker.args:
            raise pytest.UsageError("The skip_on_windows marker does not accept any arguments")
        reason = skip_on_windows_marker.kwargs.pop("reason", None)
        if skip_on_windows_marker.kwargs:
            raise pytest.UsageError(
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
            raise pytest.UsageError(
                "The skip_unless_on_windows marker does not accept any arguments"
            )
        reason = skip_unless_on_windows_marker.kwargs.pop("reason", None)
        if skip_unless_on_windows_marker.kwargs:
            raise pytest.UsageError(
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
            raise pytest.UsageError("The skip_on_linux marker does not accept any arguments")
        reason = skip_on_linux_marker.kwargs.pop("reason", None)
        if skip_on_linux_marker.kwargs:
            raise pytest.UsageError(
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
            raise pytest.UsageError("The skip_unless_on_linux marker does not accept any arguments")
        reason = skip_unless_on_linux_marker.kwargs.pop("reason", None)
        if skip_unless_on_linux_marker.kwargs:
            raise pytest.UsageError(
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
            raise pytest.UsageError("The skip_on_darwin marker does not accept any arguments")
        reason = skip_on_darwin_marker.kwargs.pop("reason", None)
        if skip_on_darwin_marker.kwargs:
            raise pytest.UsageError(
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
            raise pytest.UsageError(
                "The skip_unless_on_darwin marker does not accept any arguments"
            )
        reason = skip_unless_on_darwin_marker.kwargs.pop("reason", None)
        if skip_unless_on_darwin_marker.kwargs:
            raise pytest.UsageError(
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
            raise pytest.UsageError("The skip_on_sunos marker does not accept any arguments")
        reason = skip_on_sunos_marker.kwargs.pop("reason", None)
        if skip_on_sunos_marker.kwargs:
            raise pytest.UsageError(
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
            raise pytest.UsageError("The skip_unless_on_sunos marker does not accept any arguments")
        reason = skip_unless_on_sunos_marker.kwargs.pop("reason", None)
        if skip_unless_on_sunos_marker.kwargs:
            raise pytest.UsageError(
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
            raise pytest.UsageError("The skip_on_smartos marker does not accept any arguments")
        reason = skip_on_smartos_marker.kwargs.pop("reason", None)
        if skip_on_smartos_marker.kwargs:
            raise pytest.UsageError(
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
            raise pytest.UsageError(
                "The skip_unless_on_smartos marker does not accept any arguments"
            )
        reason = skip_unless_on_smartos_marker.kwargs.pop("reason", None)
        if skip_unless_on_smartos_marker.kwargs:
            raise pytest.UsageError(
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
            raise pytest.UsageError("The skip_on_freebsd marker does not accept any arguments")
        reason = skip_on_freebsd_marker.kwargs.pop("reason", None)
        if skip_on_freebsd_marker.kwargs:
            raise pytest.UsageError(
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
            raise pytest.UsageError(
                "The skip_unless_on_freebsd marker does not accept any arguments"
            )
        reason = skip_unless_on_freebsd_marker.kwargs.pop("reason", None)
        if skip_unless_on_freebsd_marker.kwargs:
            raise pytest.UsageError(
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
            raise pytest.UsageError("The skip_on_netbsd marker does not accept any arguments")
        reason = skip_on_netbsd_marker.kwargs.pop("reason", None)
        if skip_on_netbsd_marker.kwargs:
            raise pytest.UsageError(
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
            raise pytest.UsageError(
                "The skip_unless_on_netbsd marker does not accept any arguments"
            )
        reason = skip_unless_on_netbsd_marker.kwargs.pop("reason", None)
        if skip_unless_on_netbsd_marker.kwargs:
            raise pytest.UsageError(
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
            raise pytest.UsageError("The skip_on_openbsd marker does not accept any arguments")
        reason = skip_on_openbsd_marker.kwargs.pop("reason", None)
        if skip_on_openbsd_marker.kwargs:
            raise pytest.UsageError(
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
            raise pytest.UsageError(
                "The skip_unless_on_openbsd marker does not accept any arguments"
            )
        reason = skip_unless_on_openbsd_marker.kwargs.pop("reason", None)
        if skip_unless_on_openbsd_marker.kwargs:
            raise pytest.UsageError(
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
            raise pytest.UsageError("The skip_on_aix marker does not accept any arguments")
        reason = skip_on_aix_marker.kwargs.pop("reason", None)
        if skip_on_aix_marker.kwargs:
            raise pytest.UsageError(
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
            raise pytest.UsageError("The skip_unless_on_aix marker does not accept any arguments")
        reason = skip_unless_on_aix_marker.kwargs.pop("reason", None)
        if skip_unless_on_aix_marker.kwargs:
            raise pytest.UsageError(
                "The skip_unless_on_aix marker only accepts 'reason' as a keyword argument."
            )
        if reason is None:
            reason = "Platform is not AIX, skipped"
        if not saltfactories.utils.platform.is_aix():
            item._skipped_by_mark = True
            pytest.skip(reason)

    skip_on_aarch64_marker = item.get_closest_marker("skip_on_aarch64")
    if skip_on_aarch64_marker is not None:
        if skip_on_aarch64_marker.args:
            raise pytest.UsageError("The skip_on_aarch64 marker does not accept any arguments")
        reason = skip_on_aarch64_marker.kwargs.pop("reason", None)
        if skip_on_aarch64_marker.kwargs:
            raise pytest.UsageError(
                "The skip_on_aarch64 marker only accepts 'reason' as a keyword argument."
            )
        if reason is None:
            reason = "Skipped on AArch64"
        if saltfactories.utils.platform.is_aarch64():
            item._skipped_by_mark = True
            pytest.skip(reason)

    skip_unless_on_aarch64_marker = item.get_closest_marker("skip_unless_on_aarch64")
    if skip_unless_on_aarch64_marker is not None:
        if skip_unless_on_aarch64_marker.args:
            raise pytest.UsageError(
                "The skip_unless_on_aarch64 marker does not accept any arguments"
            )
        reason = skip_unless_on_aarch64_marker.kwargs.pop("reason", None)
        if skip_unless_on_aarch64_marker.kwargs:
            raise pytest.UsageError(
                "The skip_unless_on_aarch64 marker only accepts 'reason' as a keyword argument."
            )
        if reason is None:
            reason = "Platform is not AArch64, skipped"
        if not saltfactories.utils.platform.is_aarch64():
            item._skipped_by_mark = True
            pytest.skip(reason)

    skip_on_platforms_marker = item.get_closest_marker("skip_on_platforms")
    if skip_on_platforms_marker is not None:
        if skip_on_platforms_marker.args:
            raise pytest.UsageError("The skip_on_platforms marker does not accept any arguments")
        reason = skip_on_platforms_marker.kwargs.pop("reason", None)
        if not skip_on_platforms_marker.kwargs:
            raise pytest.UsageError(
                "Pass at least one platform to skip_on_platforms as a keyword argument"
            )
        if not any(skip_on_platforms_marker.kwargs.values()):
            raise pytest.UsageError(
                "Pass at least one platform with a True value to skip_on_platforms as a keyword argument"
            )
        if reason is None:
            reason = "Skipped on platform match"
        try:
            if saltfactories.utils.platform.on_platforms(**skip_on_platforms_marker.kwargs):
                item._skipped_by_mark = True
                pytest.skip(reason)
        except TypeError as exc:
            raise pytest.UsageError(
                "Passed an invalid platform to skip_on_platforms: {}".format(exc)
            )

    skip_unless_on_platforms_marker = item.get_closest_marker("skip_unless_on_platforms")
    if skip_unless_on_platforms_marker is not None:
        if skip_unless_on_platforms_marker.args:
            raise pytest.UsageError(
                "The skip_unless_on_platforms marker does not accept any arguments"
            )
        reason = skip_unless_on_platforms_marker.kwargs.pop("reason", None)
        if not skip_unless_on_platforms_marker.kwargs:
            raise pytest.UsageError(
                "Pass at least one platform to skip_unless_on_platforms as a keyword argument"
            )
        if not any(skip_unless_on_platforms_marker.kwargs.values()):
            raise pytest.UsageError(
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
            raise pytest.UsageError(
                "Passed an invalid platform to skip_unless_on_platforms: {}".format(exc)
            )

    # Next are two special markers, requires_salt_modules and requires_salt_states. These need access to a
    # saltfactories.utils.functional.Loader instance
    # They will use a session_markers_loader fixture to gain access to that
    requires_salt_modules_marker = item.get_closest_marker("requires_salt_modules")
    if requires_salt_modules_marker is not None:
        if requires_salt_modules_marker.kwargs:
            raise pytest.UsageError(
                "The 'required_salt_modules' marker does not accept keyword arguments"
            )
        required_salt_modules = requires_salt_modules_marker.args
        if not required_salt_modules:
            raise pytest.UsageError(
                "The 'required_salt_modules' marker needs at least one module name to be passed"
            )
        for arg in required_salt_modules:
            if not isinstance(arg, str):
                raise pytest.UsageError(
                    "The 'required_salt_modules' marker only accepts strings as arguments"
                )
        session_markers_loader = item._request.getfixturevalue("session_markers_loader")
        required_salt_modules = set(required_salt_modules)
        not_available_modules = check_required_loader_attributes(
            session_markers_loader, "modules", required_salt_modules
        )

        if not_available_modules:
            item._skipped_by_mark = True
            if len(not_available_modules) == 1:
                pytest.skip("Salt module '{}' is not available".format(*not_available_modules))
            pytest.skip("Salt modules not available: {}".format(", ".join(not_available_modules)))

    requires_salt_states_marker = item.get_closest_marker("requires_salt_states")
    if requires_salt_states_marker is not None:
        if requires_salt_states_marker.kwargs:
            raise pytest.UsageError(
                "The 'required_salt_states' marker does not accept keyword arguments"
            )
        required_salt_states = requires_salt_states_marker.args
        if not required_salt_states:
            raise pytest.UsageError(
                "The 'required_salt_states' marker needs at least one state module name to be passed"
            )
        for arg in required_salt_states:
            if not isinstance(arg, str):
                raise pytest.UsageError(
                    "The 'required_salt_states' marker only accepts strings as arguments"
                )
        session_markers_loader = item._request.getfixturevalue("session_markers_loader")
        required_salt_states = set(required_salt_states)
        not_available_states = check_required_loader_attributes(
            session_markers_loader, "states", required_salt_states
        )

        if not_available_states:
            item._skipped_by_mark = True
            if len(not_available_states) == 1:
                pytest.skip("Salt state module '{}' is not available".format(*not_available_states))
            pytest.skip(
                "Salt state modules not available: {}".format(", ".join(not_available_states))
            )
