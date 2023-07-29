"""
Salt's Loader PyTest Mock Support.
"""
import logging
import sys
import types
from collections import deque
from unittest.mock import patch

import attr
import pytest
from pytestshellutils.utils import format_callback_to_string

try:
    LOGGING_TRACE_LEVEL = logging.TRACE
except AttributeError:
    # Salt's logging hasn't been setup yet
    LOGGING_TRACE_LEVEL = 5

log = logging.getLogger(__name__)


@attr.s(init=True, slots=True, frozen=True)
class LoaderModuleMock:
    """
    Salt Loader mock class.
    """

    setup_loader_modules = attr.ib(init=True)
    # These dunders should always exist at the module global scope
    salt_module_dunders = attr.ib(
        init=True,
        repr=False,
        kw_only=True,
        default=(
            "__opts__",
            "__salt__",
            "__runner__",
            "__context__",
            "__utils__",
            "__ext_pillar__",
            "__thorium__",
            "__states__",
            "__serializers__",
            "__ret__",
            "__grains__",
            "__pillar__",
            "__sdb__",
        ),
    )
    # These dunders might exist at the module global scope
    salt_module_dunders_optional = attr.ib(
        init=True,
        repr=False,
        kw_only=True,
        default=("__proxy__",),
    )
    # These dunders might exist at the function global scope
    salt_module_dunder_attributes = attr.ib(
        init=True,
        repr=False,
        kw_only=True,
        default=(
            # Salt states attributes
            "__env__",
            "__low__",
            "__instance_id__",
            "__orchestration_jid__",
            # Salt runners attributes
            "__jid_event__",
            # Salt cloud attributes
            "__active_provider_name__",
            # Proxy Minions
            "__proxyenabled__",
        ),
    )
    _finalizers = attr.ib(init=False, repr=False, hash=False, default=attr.Factory(deque))

    def start(self):
        """
        Start mocks.
        """
        module_globals = {dunder: {} for dunder in self.salt_module_dunders}
        for module, globals_to_mock in self.setup_loader_modules.items():
            log.log(
                LOGGING_TRACE_LEVEL,
                "Setting up loader globals for %s; globals: %s",
                module,
                globals_to_mock,
            )
            if not isinstance(module, types.ModuleType):
                msg = (
                    "The dictionary keys returned by setup_loader_modules() must be an imported module, "
                    f"not {type(module)}"
                )
                raise pytest.UsageError(msg)
            if not isinstance(globals_to_mock, dict):
                msg = (
                    "The dictionary values returned by setup_loader_modules() must be a dictionary, "
                    f"not {type(globals_to_mock)}"
                )
                raise pytest.UsageError(msg)

            # Patch sys.modules as the first step
            if "sys.modules" in globals_to_mock:
                self._patch_sys_modules(globals_to_mock)

            # Now patch the module globals
            self._patch_module_globals(module, globals_to_mock, module_globals.copy())

    def stop(self):
        """
        Stop mocks.
        """
        while self._finalizers:
            func, args, kwargs = self._finalizers.popleft()
            func_repr = format_callback_to_string(func, args, kwargs)
            try:
                log.log(LOGGING_TRACE_LEVEL, "Calling finalizer %s", func_repr)
                func(*args, **kwargs)
            except Exception:  # pragma: no cover pylint: disable=broad-except
                log.exception("Failed to run finalizer %s", func_repr)

    def addfinalizer(self, func, *args, **kwargs):
        """
        Register a function to run when stopping.
        """
        self._finalizers.append((func, args, kwargs))

    def _patch_sys_modules(self, mocks):
        sys_modules = mocks["sys.modules"]
        if not isinstance(sys_modules, dict):
            msg = f"'sys.modules' must be a dictionary not: {type(sys_modules)}"
            raise pytest.UsageError(msg)
        patcher = patch.dict(sys.modules, values=sys_modules)
        patcher.start()
        self.addfinalizer(patcher.stop)

    def _patch_module_globals(self, module, mocks, module_globals):
        salt_dunder_dicts = self.salt_module_dunders + self.salt_module_dunders_optional
        allowed_salt_dunders = salt_dunder_dicts + self.salt_module_dunder_attributes
        for key in mocks:
            if key == "sys.modules":
                # sys.modules is addressed on another function
                continue

            if key.startswith("__"):
                if key in ("__init__", "__virtual__"):
                    msg = f"No need to patch {key!r}. Passed loader module dict: {self.setup_loader_modules}"
                    raise pytest.UsageError(msg)
                if key not in allowed_salt_dunders:
                    msg = f"Don't know how to handle {key!r}. Passed loader module dict: {self.setup_loader_modules}"
                    raise pytest.UsageError(msg)
            module_globals[key] = mocks[key]

        # Patch the module!
        log.log(LOGGING_TRACE_LEVEL, "Patching globals for %s; globals: %s", module, module_globals)
        patcher = patch.multiple(module, create=True, **module_globals)
        patcher.start()
        self.addfinalizer(patcher.stop)

    def __enter__(self):
        """
        Use the mock class as a context manager.
        """
        self.start()
        return self

    def __exit__(self, *_):
        """
        Exit context manager.
        """
        self.stop()
