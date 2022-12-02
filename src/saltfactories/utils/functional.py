"""
Salt functional testing support.
"""
import copy
import logging
import operator
import pathlib
import shutil
from unittest import mock

import attr
from pytestshellutils.utils import format_callback_to_string
from pytestshellutils.utils.processes import MatchString


PATCH_TARGET = "salt.loader.lazy.LOADED_BASE_NAME"

log = logging.getLogger(__name__)


class Loaders:
    """
    This class provides the required functionality for functional testing against the salt loaders.

    :param dict opts:
        The options dictionary to load the salt loaders.

    Example usage:

    .. code-block:: python

        import salt.config
        from saltfactories.utils.functional import Loaders


        @pytest.fixture(scope="module")
        def minion_opts():
            return salt.config.minion_config(None)


        @pytest.fixture(scope="module")
        def loaders(minion_opts):
            return Loaders(minion_opts)


        @pytest.fixture(autouse=True)
        def reset_loaders_state(loaders):
            try:
                # Run the tests
                yield
            finally:
                # Reset the loaders state
                loaders.reset_state()
    """

    def __init__(self, opts, loaded_base_name=None):
        if loaded_base_name is None:
            from salt.loader.lazy import LOADED_BASE_NAME

            loaded_base_name = LOADED_BASE_NAME
        self.opts = opts
        self.loaded_base_name = loaded_base_name
        self.context = {}
        self._cachedir = pathlib.Path(opts["cachedir"])
        self._original_opts = copy.deepcopy(opts)
        self._reset_state_funcs = [self.context.clear, self._cleanup_cache]
        self._reload_all_funcs = [self.reset_state]
        self._grains = None
        self._modules = None
        self._pillar = None
        self._serializers = None
        self._states = None
        self._utils = None

        import salt.features

        salt.features.setup_features(self.opts)
        self.reload_all()
        # Force the minion to populate it's cache if need be
        self.modules.saltutil.sync_all()
        # Now reload again so that the loader takes into account said cache
        self.reload_all()

    def _cleanup_cache(self):
        shutil.rmtree(str(self._cachedir), ignore_errors=True)
        self._cachedir.mkdir(exist_ok=True, parents=True)

    def reset_state(self):
        """
        Reset the state functions state.
        """
        for func in self._reset_state_funcs:
            func()

    def reload_all(self):
        """
        Reload all loaders.
        """
        for func in self._reload_all_funcs:
            try:
                func()
            except Exception as exc:  # pragma: no cover pylint: disable=broad-except
                log.warning("Failed to run '%s': %s", func.__name__, exc, exc_info=True)
        if self._modules is not None:
            self._modules.clean_modules()
            self._modules.clear()
            self._modules = None
        if self._serializers is not None:
            self._serializers.clean_modules()
            self._serializers.clear()
            self._serializers = None
        if self._states is not None:
            self._states.clean_modules()
            self._states.clear()
            self._states = None
        if self._utils is not None:
            self._utils.clean_modules()
            self._utils.clear()
            self._utils = None
        self.opts = copy.deepcopy(self._original_opts)
        self._pillar = None
        self._grains = None
        self.opts["grains"] = self.grains
        self.refresh_pillar()

    @property
    def grains(self):
        """
        The grains loaded by the salt loader.
        """
        import salt.loader

        if self._grains is None:
            try:
                self._grains = salt.loader.grains(  # pylint: disable=unexpected-keyword-arg
                    self.opts,
                    context=self.context,
                    loaded_base_name=self.loaded_base_name,
                )
            except TypeError:
                # Salt < 3005
                with mock.patch(PATCH_TARGET, self.loaded_base_name):
                    self._grains = salt.loader.grains(self.opts, context=self.context)
        return self._grains

    @property
    def utils(self):
        """
        The utils loaded by the salt loader.
        """
        import salt.loader

        if self._utils is None:
            try:
                self._utils = salt.loader.utils(  # pylint: disable=unexpected-keyword-arg
                    self.opts,
                    context=self.context,
                    loaded_base_name=self.loaded_base_name,
                )
            except TypeError:
                # Salt < 3005
                with mock.patch(PATCH_TARGET, self.loaded_base_name):
                    self._utils = salt.loader.utils(self.opts, context=self.context)
        return self._utils

    @property
    def modules(self):
        """
        The execution modules loaded by the salt loader.
        """
        import salt.loader

        if self._modules is None:
            _modules = salt.loader.minion_mods(
                self.opts,
                context=self.context,
                utils=self.utils,
                initial_load=True,
                loaded_base_name=self.loaded_base_name,
            )

            class ModulesLoaderDict(_modules.mod_dict_class):
                """
                Custom class to implement wrappers.
                """

                def __setitem__(self, key, value):
                    """
                    Intercept method.

                    We hijack __setitem__ so that we can replace specific state functions with a
                    wrapper which will return a more pythonic data structure to assert against.
                    """
                    if key in (
                        "state.apply",
                        "state.high",
                        "state.highstate",
                        "state.low",
                        "state.single",
                        "state.sls",
                        "state.sls_id",
                        "state.template",
                        "state.template_str",
                        "state.test",
                        "state.top",
                    ):
                        if key in ("state.low", "state.single", "state.sls_id"):
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
        """
        The serializers loaded by the salt loader.
        """
        import salt.loader

        if self._serializers is None:
            try:
                self._serializers = (
                    salt.loader.serializers(  # pylint: disable=unexpected-keyword-arg
                        self.opts,
                        loaded_base_name=self.loaded_base_name,
                    )
                )
            except TypeError:
                # Salt < 3005
                with mock.patch(PATCH_TARGET, self.loaded_base_name):
                    self._serializers = salt.loader.serializers(self.opts)
        return self._serializers

    @property
    def states(self):
        """
        The state modules loaded by the salt loader.
        """
        import salt.loader

        if self._states is None:
            try:
                _states = salt.loader.states(  # pylint: disable=unexpected-keyword-arg
                    self.opts,
                    functions=self.modules,
                    utils=self.utils,
                    serializers=self.serializers,
                    context=self.context,
                    loaded_base_name=self.loaded_base_name,
                )
            except TypeError:
                # Salt < 3005
                with mock.patch(PATCH_TARGET, self.loaded_base_name):
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

            class StatesLoaderDict(_states.mod_dict_class):
                """
                Custom class to implement wrappers.
                """

                def __init__(self, proxy_func, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self.__proxy_func__ = proxy_func

                def __setitem__(self, name, func):
                    """
                    Intercept method.

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
        """
        The pillar loaded by the salt loader.
        """
        import salt.pillar

        if self._pillar is None:
            try:
                self._pillar = salt.pillar.get_pillar(  # pylint: disable=unexpected-keyword-arg
                    self.opts,
                    self.grains,
                    self.opts["id"],
                    saltenv=self.opts["saltenv"],
                    pillarenv=self.opts.get("pillarenv"),
                    loaded_base_name=self.loaded_base_name,
                ).compile_pillar()
            except TypeError:
                # Salt < 3005
                with mock.patch(PATCH_TARGET, self.loaded_base_name):
                    self._pillar = salt.pillar.get_pillar(
                        self.opts,
                        self.grains,
                        self.opts["id"],
                        saltenv=self.opts["saltenv"],
                        pillarenv=self.opts.get("pillarenv"),
                    ).compile_pillar()
        return self._pillar

    def refresh_pillar(self):
        """
        Refresh the pillar.
        """
        self._pillar = None
        self.opts["pillar"] = self.pillar


@attr.s
class StateResult:
    """
    This class wraps a single salt state return into a more pythonic object in order to simplify assertions.

    :param dict raw:
        A single salt state return result

    .. code-block:: python

        def test_user_absent(loaders):
            ret = loaders.states.user.absent(name=random_string("account-", uppercase=False))
            assert ret.result is True
    """

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
        """
        The ``__run_num__`` key on the full state return dictionary.
        """
        return self.full_return["__run_num__"] or 0

    @property
    def id(self):  # pylint: disable=invalid-name
        """
        The ``__id__`` key on the full state return dictionary.
        """
        return self.full_return.get("__id__")

    @property
    def name(self):
        """
        The ``name`` key on the full state return dictionary.
        """
        return self.full_return.get("name")

    @property
    def result(self):
        """
        The ``result`` key on the full state return dictionary.
        """
        return self.full_return["result"]

    @property
    def changes(self):
        """
        The ``changes`` key on the full state return dictionary.
        """
        return self.full_return["changes"]

    @property
    def comment(self) -> MatchString:
        """
        The ``comment`` key on the full state return dictionary.
        """
        return MatchString(self.full_return["comment"])

    @property
    def warnings(self):
        """
        The ``warnings`` key on the full state return dictionary.
        """
        return self.full_return.get("warnings") or []

    def __contains__(self, key):
        """
        Checks for the existence of ``key`` in the full state return dictionary.
        """
        return key in self.full_return

    def __getitem__(self, key):
        """
        Get the value of the provided key from the state return.
        """
        try:
            return self.full_return[key]
        except KeyError:
            raise KeyError("The '{}' key was not found in the state return".format(key)) from None

    def __eq__(self, _):
        """
        Override method.
        """
        raise TypeError(
            "Please assert comparisons with {}.filtered instead".format(self.__class__.__name__)
        )

    def __bool__(self):
        """
        Override method.
        """
        raise TypeError(
            "Please assert comparisons with {}.filtered instead".format(self.__class__.__name__)
        )


@attr.s
class StateFunction:
    """
    Salt state module functions wrapper.

    Simple wrapper around Salt's state execution module functions which actually proxies the call
    through Salt's ``state.single`` execution module
    """

    proxy_func = attr.ib(repr=False)
    state_func = attr.ib()

    def __call__(self, *args, **kwargs):
        """
        Call the state module function.
        """
        log.info(
            "Calling %s",
            format_callback_to_string("state.single", (self.state_func,) + args, kwargs),
        )
        return self.proxy_func(self.state_func, *args, **kwargs)


@attr.s
class MultiStateResult:
    '''
    Multiple state returns wrapper class.

    This class wraps multiple salt state returns, for example, running the ``state.sls`` execution module,
    into a more pythonic object in order to simplify assertions

    :param dict,list raw:
        The multiple salt state returns result, a dictionary on success or a list on failure

    Example usage on the test suite:

    .. code-block:: python

        def test_issue_1876_syntax_error(loaders, state_tree, tmp_path):
            testfile = tmp_path / "issue-1876.txt"
            sls_contents = """
            {}:
              file:
                - managed
                - source: salt://testfile

              file.append:
                - text: foo
            """.format(
                testfile
            )
            with pytest.helpers.temp_file("issue-1876.sls", sls_contents, state_tree):
                ret = loaders.modules.state.sls("issue-1876")
                assert ret.failed
                errmsg = (
                    "ID '{}' in SLS 'issue-1876' contains multiple state declarations of the"
                    " same type".format(testfile)
                )
                assert errmsg in ret.errors


        def test_pydsl(loaders, state_tree, tmp_path):
            testfile = tmp_path / "testfile"
            sls_contents = """
            #!pydsl

            state("{}").file("touch")
            """.format(
                testfile
            )
            with pytest.helpers.temp_file("pydsl.sls", sls_contents, state_tree):
                ret = loaders.modules.state.sls("pydsl")
                for staterun in ret:
                    assert staterun.result is True
                assert testfile.exists()
    '''

    raw = attr.ib()
    _structured = attr.ib(init=False)

    @_structured.default
    def _set_structured(self):
        if self.failed:
            return []
        state_result = [StateResult({state_id: data}) for state_id, data in self.raw.items()]
        return sorted(state_result, key=operator.attrgetter("run_num"))

    def __iter__(self):
        """
        Iterate through the state return.
        """
        return iter(self._structured)

    def __contains__(self, key):
        """
        Check the presence of ``key`` in the state return.
        """
        for state_result in self:
            if key in (state_result.id, state_result.state_id, state_result.name):
                return True
        return False

    def __getitem__(self, state_id_or_index):
        """
        Get an item from the state return.

        .. admonition:: ATTENTION

            Consider the following state:

                ```yaml
                sbclient_2_0:
                  mysql_user.present:
                    - host: localhost
                    - password: sbclient
                    - connection_user: {mysql_user}
                    - connection_pass: {mysql_pass}
                    - connection_db: mysql
                    - connection_port: {mysql_port}
                  mysql_database.present:
                    - connection_user: {mysql_user}
                    - connection_pass: {mysql_pass}
                    - connection_db: mysql
                    - connection_port: {mysql_port}
                  mysql_grants.present:
                    - grant: ALL PRIVILEGES
                    - user: sbclient_2_0
                    - database: sbclient_2_0.*
                    - host: localhost
                    - connection_user: {mysql_user}
                    - connection_pass: {mysql_pass}
                    - connection_db: mysql
                    - connection_port: {mysql_port}
                ```

                Accessing `MultiStateResult["sbclient_2_0"] will only return **one**
                of the state entries. There's three.
        """
        if isinstance(state_id_or_index, int):
            # We're trying to get the state run by index
            return self._structured[state_id_or_index]
        for state_result in self:
            if state_id_or_index in (state_result.id, state_result.state_id, state_result.name):
                return state_result
        raise KeyError("No state by the ID of '{}' was found".format(state_id_or_index))

    @property
    def failed(self):
        """
        Return ``True`` or ``False`` if the multiple state run was not successful.
        """
        return isinstance(self.raw, list)

    @property
    def errors(self):
        """
        Return the list of errors in case the multiple state run was not successful.
        """
        if not self.failed:
            return []
        return list(self.raw)


@attr.s(frozen=True)
class StateModuleFuncWrapper:
    """
    This class simply wraps a single or multiple state returns into a more pythonic object.

    :py:class:`~saltfactories.utils.functional.StateResult` or
    py:class:`~saltfactories.utils.functional.MultiStateResult`

    :param callable func:
        A salt loader function
    :param ~saltfactories.utils.functional.StateResult,~saltfactories.utils.functional.MultiStateResult wrapper:
        The wrapper to use for the return of the salt loader function's return
    """

    func = attr.ib()
    wrapper = attr.ib()

    def __call__(self, *args, **kwargs):
        """
        Call the state module function.
        """
        ret = self.func(*args, **kwargs)
        return self.wrapper(ret)
