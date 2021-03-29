"""
saltfactories.utils.functional
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Salt functional testing support
"""
import copy
import logging

import attr
import salt.loader
import salt.pillar

try:
    import salt.features

    HAS_SALT_FEATURES = True
except ImportError:  # pragma: no cover
    HAS_SALT_FEATURES = False

log = logging.getLogger(__name__)


class Loaders:
    """
    This class provides the required functionality for functional testing against the salt loaders

    :param dict opts: The options dictionary to load the salt loaders.
    """

    def __init__(self, opts):
        self.opts = opts
        self.context = {}
        self._original_opts = copy.deepcopy(opts)
        self._reset_state_funcs = [self.context.clear]
        self._reload_all_funcs = [self.reset_state]
        self._grains = None
        self._utils = None
        self._modules = None
        self._pillar = None
        self._serializers = None
        self._states = None
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
        self._grains = self._utils = self._modules = None
        self._pillar = self._serializers = self._states = None
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
            self._modules = salt.loader.minion_mods(
                self.opts, context=self.context, utils=self.utils, initial_load=True
            )
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
            _states._load_all()
            # for funcname in list(_states):
            #    _states[funcname]

            # Now, we proxy loaded modules through salt.modules.state.single
            for module_name in list(_states.loaded_modules):
                for func_name in list(_states.loaded_modules[module_name]):
                    full_func_name = "{}.{}".format(module_name, func_name)
                    replacement_function = StateFunction(self.modules.state.single, full_func_name)
                    _states._dict[full_func_name] = replacement_function
                    _states.loaded_modules[module_name][func_name] = replacement_function
                    setattr(
                        _states.loaded_modules[module_name],
                        func_name,
                        replacement_function,
                    )
            self._states = _states
        return self._states

    @property
    def pillar(self):
        if self._pillar is None:
            self._pillar = salt.pillar.get_pillar(
                self.opts,
                self.opts["grains"],
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

    def __eq__(self, _):
        raise TypeError(
            "Please assert comparissons with {}.filtered instead".format(self.__class__.__name__)
        )

    def __contains__(self, _):
        raise TypeError(
            "Please assert comparissons with {}.filtered instead".format(self.__class__.__name__)
        )

    def __bool__(self):
        raise TypeError(
            "Please assert comparissons with {}.filtered instead".format(self.__class__.__name__)
        )


@attr.s
class StateFunction:
    proxy_func = attr.ib(repr=False)
    state_func = attr.ib()

    def __call__(self, *args, **kwargs):
        name = None
        if args and len(args) == 1:
            name = args[0]
        if name is not None and "name" in kwargs:
            raise RuntimeError(
                "Either pass 'name' as the single argument to the call or remove 'name' as a keyword argument"
            )
        if name is None:
            name = kwargs.pop("name", None)
        if name is None:
            raise RuntimeError(
                "'name' was not passed as the single argument to the function nor as a keyword argument"
            )
        log.info("Calling state.single(%s, name=%s, %s)", self.state_func, name, kwargs)
        result = self.proxy_func(self.state_func, name=name, **kwargs)
        return StateResult(result)
