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

import salt.utils.path
import salt.utils.win_functions

from saltfactories.utils import ports
from saltfactories.utils import socket

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


def skip_if_binaries_missing(binaries, check_all=True, message=None):
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
        message (str):
            Message to include in the skip reason.

    Returns:
        str: The reason for the skip.
        None: Should not be skipped.
    """
    if message:
        reason = "{} ".format(message)
    else:
        reason = ""
    if check_all is False:
        # We only need one of the passed binaries to exist
        if salt.utils.path.which_bin(binaries) is None:
            reason += "None of the following binaries was found: {}".format(", ".join(binaries))
            return reason
    else:
        for binary in binaries:
            if salt.utils.path.which(binary) is None:
                reason += "The '{}' binary was not found".format(binary)
                return reason
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
    Args:
        loader_instance(:py:class:`saltfactories.utils.functional.Loader`):
            An instance of :py:class:`saltfactories.utils.functional.Loader`
        loader_attr(str): The name of the minion attribute to check, such as 'modules' or 'states'
        required_items(tuple): The items that must be part of the loader attribute for the decorated test
    Returns:
        set: The modules that are not available
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
