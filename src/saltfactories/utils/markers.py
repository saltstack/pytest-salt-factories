"""
Markers related utilities.

..
    PYTEST_DONT_REWRITE
"""
import fnmatch
import logging

import _pytest._version
import pytest

PYTEST_GE_7 = getattr(_pytest._version, "version_tuple", (-1, -1)) >= (7, 0)

log = logging.getLogger(__name__)


def check_required_loader_attributes(loader_instance, loader_attr, required_items):
    """
    Check if the salt loaders has the passed required items.

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
    Fixtures injection based on markers or test skips based on CLI arguments.
    """
    # Two special markers, requires_salt_modules and requires_salt_states. These need access to a
    # saltfactories.utils.functional.Loader instance
    # They will use a session_markers_loader fixture to gain access to that
    exc_kwargs = {}
    if PYTEST_GE_7:
        exc_kwargs["_use_item_location"] = True
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
                raise pytest.skip.Exception(
                    "Salt module '{}' is not available".format(*not_available_modules), **exc_kwargs
                )
            raise pytest.skip.Exception(
                "Salt modules not available: {}".format(", ".join(not_available_modules)),
                **exc_kwargs
            )

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
                raise pytest.skip.Exception(
                    "Salt state module '{}' is not available".format(*not_available_states),
                    **exc_kwargs
                )
            raise pytest.skip.Exception(
                "Salt state modules not available: {}".format(
                    ", ".join(not_available_states), **exc_kwargs
                )
            )
