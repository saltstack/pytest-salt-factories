"""
saltfactories.utils.functional
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Salt functional testing support
"""
import copy
import logging
import operator

import attr
import salt.loader
import salt.pillar

from saltfactories.utils import format_callback_to_string

try:
    import salt.features  # pylint: disable=ungrouped-imports

    HAS_SALT_FEATURES = True
except ImportError:  # pragma: no cover
    HAS_SALT_FEATURES = False

log = logging.getLogger(__name__)


class Loaders:
    """
    This class provides the required functionality for functional testing against the salt loaders

    :param dict opts:
        The options dictionary to load the salt loaders.
    :param ~saltfactories.utils.functional.StateFunction state_func_wrapper_cls:
        The class to use to wrap state functions
    """

    def __init__(self, opts):
        self.opts = opts
        self.context = {}
        self._original_opts = copy.deepcopy(opts)
        self._reset_state_funcs = [self.context.clear]
        self._reload_all_funcs = [self.reset_state]
        self._grains = None
        self._modules = None
        self._pillar = None
        self._serializers = None
        self._states = None
        self._utils = None
        if HAS_SALT_FEATURES:
            salt.features.setup_features(self.opts)
        self.reload_all()
        # Force the minion to populate it's cache if need be
        self.modules.saltutil.sync_all()
        # Now reload again so that the loader takes into account said cache
        self.reload_all()

    def reset_state(self):
        for func in self._reset_state_funcs:
            func()

    def reload_all(self):
        for func in self._reload_all_funcs:
            try:
                func()
            except Exception as exc:  # pragma: no cover pylint: disable=broad-except
                log.warning("Failed to run '%s': %s", func.__name__, exc, exc_info=True)
        self.opts = copy.deepcopy(self._original_opts)
        self._grains = None
        self._modules = None
        self._pillar = None
        self._serializers = None
        self._states = None
        self._utils = None
        self.opts["grains"] = self.grains
        self.refresh_pillar()

    @property
    def grains(self):
        if self._grains is None:
            self._grains = salt.loader.grains(self.opts, context=self.context)
        return self._grains

    @property
    def utils(self):
        if self._utils is None:
            self._utils = salt.loader.utils(self.opts, context=self.context)
        return self._utils

    @property
    def modules(self):
        if self._modules is None:
            _modules = salt.loader.minion_mods(
                self.opts, context=self.context, utils=self.utils, initial_load=True
            )

            if isinstance(_modules.loaded_modules, dict):
                for func_name in ("single", "sls", "template", "template_str"):
                    full_func_name = "state.{}".format(func_name)

                    if func_name == "single":
                        wrapper_cls = StateResult
                    else:
                        wrapper_cls = MultiStateResult
                    replacement_function = StateModuleFuncWrapper(
                        _modules[full_func_name], wrapper_cls
                    )

                    _modules._dict[full_func_name] = replacement_function
                    _modules.loaded_modules["state"][func_name] = replacement_function
                    setattr(
                        _modules.loaded_modules["state"],
                        func_name,
                        replacement_function,
                    )
            else:
                # Newer version of Salt where only one dictionary with the loaded functions is maintained

                class ModulesLoaderDict(_modules.mod_dict_class):
                    def __setitem__(self, key, value):
                        """
                        We hijack __setitem__ so that we can replace specific state functions with a
                        wrapper which will return a more pythonic data structure to assert against.
                        """

                        if key in (
                            "state.single",
                            "state.sls",
                            "state.template",
                            "state.template_str",
                        ):
                            if key == "state.single":
                                wrapper_cls = StateResult
                            else:
                                wrapper_cls = MultiStateResult
                            value = StateModuleFuncWrapper(value, wrapper_cls)
                        return super().__setitem__(key, value)

                loader_dict = _modules._dict.copy()
                _modules._dict = ModulesLoaderDict()
                for key, value in loader_dict.items():
                    _modules._dict[key] = value

            self._modules = _modules
        return self._modules

    @property
    def serializers(self):
        if self._serializers is None:
            self._serializers = salt.loader.serializers(self.opts)
        return self._serializers

    @property
    def states(self):
        if self._states is None:
            _states = salt.loader.states(
                self.opts,
                functions=self.modules,
                utils=self.utils,
                serializers=self.serializers,
                context=self.context,
            )
            # For state execution modules, because we'd have to almost copy/paste what salt.modules.state.single
            # does, we actually "proxy" the call through salt.modules.state.single instead of calling the state
            # execution modules directly. This was also how the non pytest test suite worked
            # Let's load all modules now

            # Now, we proxy loaded modules through salt.modules.state.single
            if isinstance(_states.loaded_modules, dict):
                # Old Salt?
                _states._load_all()
                for module_name in list(_states.loaded_modules):
                    for func_name in list(_states.loaded_modules[module_name]):
                        full_func_name = "{}.{}".format(module_name, func_name)
                        replacement_function = StateFunction(
                            self.modules.state.single, full_func_name
                        )
                        _states._dict[full_func_name] = replacement_function
                        _states.loaded_modules[module_name][func_name] = replacement_function
                        setattr(
                            _states.loaded_modules[module_name],
                            func_name,
                            replacement_function,
                        )
            else:
                # Newer version of Salt where only one dictionary with the loaded functions is maintained

                class StatesLoaderDict(_states.mod_dict_class):
                    def __init__(self, proxy_func, *args, **kwargs):
                        super().__init__(*args, **kwargs)
                        self.__proxy_func__ = proxy_func

                    def __setitem__(self, name, func):
                        """
                        We hijack __setitem__ so that we can replace the loaded functions
                        with a wrapper
                        For state execution modules, because we'd have to almost copy/paste what
                        ``salt.modules.state.single`` does, we actually "proxy" the call through
                        ``salt.modules.state.single`` instead of calling the state execution
                        modules directly. This was also how the non pytest test suite worked
                        """
                        func = StateFunction(self.__proxy_func__, name)
                        return super().__setitem__(name, func)

                loader_dict = _states._dict.copy()
                _states._dict = StatesLoaderDict(self.modules.state.single)
                for key, value in loader_dict.items():
                    _states._dict[key] = value

            self._states = _states
        return self._states

    @property
    def pillar(self):
        if self._pillar is None:
            self._pillar = salt.pillar.get_pillar(
                self.opts,
                self.grains,
                self.opts["id"],
                saltenv=self.opts["saltenv"],
                pillarenv=self.opts.get("pillarenv"),
            ).compile_pillar()
        return self._pillar

    def refresh_pillar(self):
        self._pillar = None
        self.opts["pillar"] = self.pillar


@attr.s
class StateResult:
    raw = attr.ib()
    state_id = attr.ib(init=False)
    full_return = attr.ib(init=False)
    filtered = attr.ib(init=False)

    @state_id.default
    def _state_id(self):
        if not isinstance(self.raw, dict):
            raise ValueError("The state result errored: {}".format(self.raw))
        return next(iter(self.raw.keys()))

    @full_return.default
    def _full_return(self):
        return self.raw[self.state_id]

    @filtered.default
    def _filtered_default(self):
        _filtered = {}
        for key, value in self.full_return.items():
            if key.startswith("_") or key in ("duration", "start_time"):
                continue
            _filtered[key] = value
        return _filtered

    @property
    def run_num(self):
        return self.full_return["__run_num__"]

    @property
    def name(self):
        return self.full_return["name"]

    @property
    def result(self):
        return self.full_return["result"]

    @property
    def changes(self):
        return self.full_return["changes"]

    @property
    def comment(self):
        return self.full_return["comment"]

    @property
    def warnings(self):
        return self.full_return.get("warnings") or []

    def __contains__(self, value):
        return value in self.full_return

    def __eq__(self, _):
        raise TypeError(
            "Please assert comparisons with {}.filtered instead".format(self.__class__.__name__)
        )

    def __bool__(self):
        raise TypeError(
            "Please assert comparisons with {}.filtered instead".format(self.__class__.__name__)
        )


@attr.s
class StateFunction:
    proxy_func = attr.ib(repr=False)
    state_func = attr.ib()

    def __call__(self, *args, **kwargs):
        log.info(
            "Calling %s",
            format_callback_to_string("state.single", (self.state_func,) + args, kwargs),
        )
        return self.proxy_func(self.state_func, *args, **kwargs)


@attr.s
class MultiStateResult:
    raw = attr.ib()
    _structured = attr.ib(init=False)

    @_structured.default
    def _set_structured(self):
        if self.failed:
            return []
        state_result = [StateResult({state_id: data}) for state_id, data in self.raw.items()]
        return sorted(state_result, key=operator.attrgetter("run_num"))

    def __iter__(self):
        return iter(self._structured)

    def __contains__(self, key):
        for state_result in self:
            if state_result.state_id == key:
                return True
        return False

    def __getitem__(self, state_id_or_index):
        if isinstance(state_id_or_index, int):
            # We're trying to get the state run by index
            return self._structured[state_id_or_index]
        for state_result in self:
            if state_result.state_id == state_id_or_index:
                return state_result
        raise KeyError("No state by the ID of '{}' was found".format(state_id_or_index))

    @property
    def failed(self):
        return isinstance(self.raw, list)

    @property
    def errors(self):
        if not self.failed:
            return []
        return list(self.raw)


@attr.s(frozen=True)
class StateModuleFuncWrapper:
    func = attr.ib()
    wrapper = attr.ib()

    def __call__(self, *args, **kwargs):
        ret = self.func(*args, **kwargs)
        return self.wrapper(ret)
