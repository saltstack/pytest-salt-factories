"""
..
    PYTEST_DONT_REWRITE


saltfactories.factories.manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Salt Factories Manager
"""
import logging
import pathlib
import sys

import attr
import psutil
import salt.utils.dictupdate

import saltfactories.utils.processes.helpers
from saltfactories.factories import cli
from saltfactories.factories import daemons
from saltfactories.utils import cli_scripts
from saltfactories.utils import event_listener
from saltfactories.utils import running_username
from saltfactories.utils.ports import get_unused_localhost_port

log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True)
class FactoriesManager:
    """
    The :class:`FactoriesManager` is responsible for configuring and spawning Salt Daemons and
    making sure that any salt CLI tools are "targeted" to the right daemon.

    It also keeps track of which daemons were started and adds their termination routines to PyTest's
    request finalization routines.

    If process statistics are enabled, it also adds the started daemons to those statistics.

    Args:
        pytestconfig (:fixture:`pytestconfig`):
            PyTest `pytestconfig` fixture
        root_dir:
        log_server_port(int):
            The port the log server should listen at
        log_server_level(int):
            The level of the log server
        log_server_host(str):
            The hostname/ip address of the host running the logs server. Defaults to "localhost".
        code_dir(str):
            The path to the code root directory of the project being tested. This is important for proper
            code-coverage paths.
        inject_coverage(bool):
            Inject code-coverage related code in the generated CLI scripts
        inject_sitecustomize(bool):
            Inject code in the generated CLI scripts in order for our `sitecustomise.py` to be loaded by
            subprocesses.
        cwd(str):
            The path to the current working directory
        environ(dict):
            A dictionary of `key`, `value` pairs to add to the environment.
        slow_stop(bool):
            Whether to terminate the processes by sending a :py:attr:`SIGTERM` signal or by calling
            :py:meth:`~subprocess.Popen.terminate` on the sub-process.
            When code coverage is enabled, one will want `slow_stop` set to `True` so that coverage data
            can be written down to disk.
        start_timeout(int):
            The amount of time, in seconds, to wait, until a subprocess is considered as not started.
        stats_processes(:py:class:`~collections.OrderedDict`):
            This will be an `OrderedDict` instantiated on the :py:func:`~_pytest.hookspec.pytest_sessionstart`
            hook accessible at `stats_processes` on the `session` attribute of the :fixture:`request`.
    """

    pytestconfig = attr.ib(repr=False)
    root_dir = attr.ib()
    log_server_port = attr.ib(default=None)
    log_server_level = attr.ib(default=None)
    log_server_host = attr.ib(default=None)
    code_dir = attr.ib(default=None)
    inject_coverage = attr.ib(default=False)
    inject_sitecustomize = attr.ib(default=False)
    cwd = attr.ib(default=None)
    environ = attr.ib(default=None)
    slow_stop = attr.ib(default=True)
    start_timeout = attr.ib(default=None)
    stats_processes = attr.ib(default=None)

    # Internal attributes
    cache = attr.ib(default=None, init=False, repr=False)
    scripts_dir = attr.ib(default=None, init=False, repr=False)
    event_listener = attr.ib(default=None, init=False, repr=False)

    def __attrs_post_init__(self):
        self.root_dir = pathlib.Path(self.root_dir.strpath)
        self.root_dir.mkdir(exist_ok=True)
        if self.log_server_port is None:
            self.log_server_port = get_unused_localhost_port()
        if self.log_server_level is None:
            self.log_server_level = "error"
        if self.log_server_host is None:
            self.log_server_host = "localhost"
        if self.start_timeout is None:
            if not sys.platform.startswith(("win", "darwin")):
                self.start_timeout = 30
            else:
                # Windows and macOS are just slower
                self.start_timeout = 120

        # Setup the internal attributes
        self.scripts_dir = self.root_dir / "scripts"
        self.scripts_dir.mkdir(exist_ok=True)
        self.cache = {
            "api": {},
            "cloud": {},
            "masters": {},
            "minions": {},
            "syndics": {},
            "proxy_minions": {},
            "factories": {},
        }
        self.event_listener = event_listener.EventListener(
            auth_events_callback=self._handle_auth_event
        )
        self.event_listener.start()

    @staticmethod
    def get_salt_log_handlers_path():
        """
        Returns the path to the Salt log handler this plugin provides
        """
        return saltfactories.CODE_ROOT_DIR / "utils" / "salt" / "log_handlers"

    @staticmethod
    def get_salt_engines_path():
        """
        Returns the path to the Salt engine this plugin provides
        """
        return saltfactories.CODE_ROOT_DIR / "utils" / "salt" / "engines"

    def final_minion_config_tweaks(self, config):
        self.final_common_config_tweaks(config, "minion")

    def final_master_config_tweaks(self, config):
        pytest_key = "pytest-master"
        if pytest_key not in config:
            config[pytest_key] = {}
        config[pytest_key]["returner_address"] = self.event_listener.address
        self.final_common_config_tweaks(config, "master")

    def final_syndic_config_tweaks(self, config):
        self.final_common_config_tweaks(config, "syndic")

    def final_proxy_minion_config_tweaks(self, config):
        self.final_common_config_tweaks(config, "minion")

    def final_cloud_config_tweaks(self, config):
        self.final_common_config_tweaks(config, "cloud")

    def final_common_config_tweaks(self, config, role):
        config.setdefault("engines", [])
        if "pytest" not in config["engines"]:
            config["engines"].append("pytest")

        if "engines_dirs" not in config:
            config["engines_dirs"] = []
        config["engines_dirs"].insert(0, str(FactoriesManager.get_salt_engines_path()))
        config.setdefault("user", running_username())
        if not config["user"]:
            # If this value is empty, None, False, just remove it
            config.pop("user")
        if "log_forwarding_consumer" not in config:
            # Still using old logging, let's add our custom log handler
            if "log_handlers_dirs" not in config:
                config["log_handlers_dirs"] = []
            config["log_handlers_dirs"].insert(
                0, str(FactoriesManager.get_salt_log_handlers_path())
            )

        pytest_key = "pytest-{}".format(role)
        if pytest_key not in config:
            config[pytest_key] = {}

        pytest_config = config[pytest_key]
        if "log" not in pytest_config:
            pytest_config["log"] = {}

        log_config = pytest_config["log"]
        log_config.setdefault("host", self.log_server_host)
        log_config.setdefault("port", self.log_server_port)
        log_config.setdefault("level", self.log_server_level)

    def get_salt_master_daemon(
        self,
        master_id,
        order_masters=False,
        master_of_masters_id=None,
        config_defaults=None,
        config_overrides=None,
        max_start_attempts=3,
        start_timeout=None,
        factory_class=daemons.master.SaltMasterFactory,
        **factory_class_kwargs
    ):
        """
        Configure a salt-master

        Args:
            master_id(str):
                The master ID
            order_masters(bool):
                Boolean flag to set if this master is going to control other masters(ie, master of masters), like,
                for example, in a :ref:`Syndic <salt:syndic>` topology scenario
            master_of_masters_id(str):
                The master of masters ID, like, for example, in a :ref:`Syndic <salt:syndic>` topology scenario
            config_defaults(dict):
                A dictionary of default configuration to use when configuring the master
            config_overrides(dict):
                A dictionary of configuration overrides to use when configuring the master
            max_start_attempts(int):
                How many attempts should be made to start the master in case of failure to validate that its running
            extra_factory_class_kwargs(dict):
                Extra keyword arguments to pass to :py:class:`saltfactories.factories.daemons.master.SaltMasterFactory`

        Returns:
            :py:class:`saltfactories.factories.daemons.master.SaltMasterFactory`:
                The master process class instance
        """
        if master_id in self.cache["masters"]:
            return self.cache["masters"][master_id]

        root_dir = self._get_root_dir_for_daemon(master_id, config_defaults=config_defaults)

        _config_defaults = self.pytestconfig.hook.pytest_saltfactories_master_configuration_defaults(
            factories_manager=self,
            root_dir=root_dir,
            master_id=master_id,
            order_masters=order_masters,
        )
        if config_defaults:
            if _config_defaults:
                salt.utils.dictupdate.update(_config_defaults, config_defaults)
            else:
                _config_defaults = config_defaults.copy()

        _config_overrides = self.pytestconfig.hook.pytest_saltfactories_master_configuration_overrides(
            factories_manager=self,
            root_dir=root_dir,
            master_id=master_id,
            config_defaults=_config_defaults,
            order_masters=order_masters,
        )
        if config_overrides:
            if _config_overrides:
                salt.utils.dictupdate.update(_config_overrides, config_overrides)
            else:
                _config_overrides = config_overrides.copy()

        if master_of_masters_id:
            master_of_masters = self.cache["masters"].get(master_of_masters_id)
            if master_of_masters is None:
                raise RuntimeError("No config found for {}".format(master_of_masters_id))
            master_of_masters_config = master_of_masters.config
            if config_overrides is None:
                config_overrides = {}
            config_overrides["syndic_master"] = master_of_masters_config["interface"]
            config_overrides["syndic_master_port"] = master_of_masters_config["ret_port"]

        master_config = factory_class.default_config(
            root_dir,
            master_id=master_id,
            config_defaults=_config_defaults,
            config_overrides=_config_overrides,
            order_masters=order_masters,
        )
        self.final_master_config_tweaks(master_config)
        master_config = self.pytestconfig.hook.pytest_saltfactories_master_write_configuration(
            master_config=master_config
        )
        self.pytestconfig.hook.pytest_saltfactories_master_verify_configuration(
            master_config=master_config, username=running_username(),
        )
        return self._get_factory_class_instance(
            "salt-master",
            master_config,
            factory_class,
            "masters",
            master_id,
            max_start_attempts,
            start_timeout,
        )

    def get_salt_minion_daemon(
        self,
        minion_id,
        master_id=None,
        config_defaults=None,
        config_overrides=None,
        max_start_attempts=3,
        start_timeout=None,
        factory_class=daemons.minion.SaltMinionFactory,
        **factory_class_kwargs
    ):
        """
        Spawn a salt-minion

        Args:
            minion_id(str):
                The minion ID
            master_id(str):
                The master ID this minion will connect to.
            config_defaults(dict):
                A dictionary of default configuration to use when configuring the minion
            config_overrides(dict):
                A dictionary of configuration overrides to use when configuring the minion
            max_start_attempts(int):
                How many attempts should be made to start the minion in case of failure to validate that its running
            extra_factory_class_kwargs(dict):
                Extra keyword arguments to pass to :py:class:`~saltfactories.factories.daemons.minion.SaltMinionFactory`

        Returns:
            :py:class:`~saltfactories.factories.daemons.minion.SaltMinionFactory`:
                The minion process class instance
        """
        if minion_id in self.cache["minions"]:
            return self.cache["minions"][minion_id]

        root_dir = self._get_root_dir_for_daemon(minion_id, config_defaults=config_defaults)

        master_port = None
        if master_id is not None:
            master_config = self.cache["masters"][master_id].config
            master_port = master_config.get("ret_port")

        _config_defaults = self.pytestconfig.hook.pytest_saltfactories_minion_configuration_defaults(
            factories_manager=self, root_dir=root_dir, minion_id=minion_id, master_port=master_port,
        )
        if config_defaults:
            if _config_defaults:
                salt.utils.dictupdate.update(_config_defaults, config_defaults)
            else:
                _config_defaults = config_defaults.copy()

        _config_overrides = self.pytestconfig.hook.pytest_saltfactories_minion_configuration_overrides(
            factories_manager=self,
            root_dir=root_dir,
            minion_id=minion_id,
            config_defaults=_config_defaults,
        )
        if config_overrides:
            if _config_overrides:
                salt.utils.dictupdate.update(_config_overrides, config_overrides)
            else:
                _config_overrides = config_overrides.copy()

        minion_config = factory_class.default_config(
            root_dir,
            minion_id=minion_id,
            config_defaults=_config_defaults,
            config_overrides=_config_overrides,
            master_port=master_port,
        )
        self.final_minion_config_tweaks(minion_config)
        minion_config = self.pytestconfig.hook.pytest_saltfactories_minion_write_configuration(
            minion_config=minion_config
        )
        self.pytestconfig.hook.pytest_saltfactories_minion_verify_configuration(
            minion_config=minion_config, username=running_username(),
        )
        if master_id:
            # The in-memory minion config dictionary will hold a copy of the master config
            # in order to listen to start events so that we can confirm the minion is up, running
            # and accepting requests
            minion_config["pytest-minion"]["master_config"] = self.cache["masters"][
                master_id
            ].config

        return self._get_factory_class_instance(
            "salt-minion",
            minion_config,
            factory_class,
            "minions",
            minion_id,
            max_start_attempts,
            start_timeout,
            **factory_class_kwargs,
        )

    def get_salt_syndic_daemon(
        self,
        syndic_id,
        master_of_masters_id=None,
        config_defaults=None,
        config_overrides=None,
        max_start_attempts=3,
        start_timeout=None,
        factory_class=daemons.syndic.SaltSyndicFactory,
        **extra_factory_class_kwargs
    ):
        """
        Spawn a salt-syndic

        Args:
            syndic_id(str):
                The Syndic ID. This ID will be shared by the ``salt-master``, ``salt-minion`` and ``salt-syndic``
                processes.
            master_of_masters_id(str):
                The master of masters ID that the master configured in this :ref:`Syndic <salt:syndic>` topology
                scenario shall connect to.
            config_defaults(dict):
                A dictionary of default configurations with three top level keys, ``master``, ``minion`` and
                ``syndic``, to use when configuring the  ``salt-master``, ``salt-minion`` and ``salt-syndic``
                respectively.
            config_overrides(dict):
                A dictionary of configuration overrides with three top level keys, ``master``, ``minion`` and
                ``syndic``, to use when configuring the  ``salt-master``, ``salt-minion`` and ``salt-syndic``
                respectively.
            max_start_attempts(int):
                How many attempts should be made to start the syndic in case of failure to validate that its running
            extra_factory_class_kwargs(dict):
                Extra keyword arguments to pass to :py:class:`~saltfactories.factories.daemons.syndic.SaltSyndicFactory`

        Returns:
            :py:class:`~saltfactories.factories.daemons.syndic.SaltSyndicFactory`:
                The syndic process class instance
        """
        if syndic_id in self.cache["syndics"]:
            return self.cache["syndics"][syndic_id]
        elif syndic_id in self.cache["masters"]:
            raise RuntimeError(
                "A master by the ID of '{}' was already configured".format(syndic_id)
            )
        elif syndic_id in self.cache["minions"]:
            raise RuntimeError(
                "A minion by the ID of '{}' was already configured".format(syndic_id)
            )

        master_of_masters = self.cache["masters"].get(master_of_masters_id)
        if master_of_masters is None and master_of_masters_id:
            master_of_masters = self.get_salt_master_daemon(
                master_of_masters_id, order_masters=True
            )
        master_of_masters_config = master_of_masters.config

        syndic_master_port = master_of_masters_config["ret_port"]

        root_dir = self._get_root_dir_for_daemon(
            syndic_id, config_defaults=config_defaults.get("syndic") if config_defaults else None
        )

        defaults_and_overrides_top_level_keys = {"master", "minion", "syndic"}

        _config_defaults = self.pytestconfig.hook.pytest_saltfactories_syndic_configuration_defaults(
            factories_manager=self,
            root_dir=root_dir,
            syndic_id=syndic_id,
            syndic_master_port=syndic_master_port,
        )
        if _config_defaults and not set(_config_defaults).issubset(
            defaults_and_overrides_top_level_keys
        ):
            raise RuntimeError(
                "The config defaults returned by pytest_saltfactories_syndic_configuration_defaults must "
                "only contain 3 top level keys: {}".format(
                    ", ".join(defaults_and_overrides_top_level_keys)
                )
            )
        if config_defaults:
            if not set(config_defaults).issubset(defaults_and_overrides_top_level_keys):
                raise RuntimeError(
                    "The config_defaults keyword argument must only contain 3 top level keys: {}".format(
                        ", ".join(defaults_and_overrides_top_level_keys)
                    )
                )
            if _config_defaults:
                salt.utils.dictupdate.update(_config_defaults, config_defaults)
            else:
                _config_defaults = config_defaults.copy()

        _config_overrides = self.pytestconfig.hook.pytest_saltfactories_syndic_configuration_overrides(
            factories_manager=self,
            root_dir=root_dir,
            syndic_id=syndic_id,
            config_defaults=_config_defaults,
        )
        if _config_overrides and not set(_config_overrides).issubset(
            defaults_and_overrides_top_level_keys
        ):
            raise RuntimeError(
                "The config overrides returned by pytest_saltfactories_syndic_configuration_overrides must "
                "only contain 3 top level keys: {}".format(
                    ", ".join(defaults_and_overrides_top_level_keys)
                )
            )
        if config_overrides:
            if not set(config_overrides).issubset(defaults_and_overrides_top_level_keys):
                raise RuntimeError(
                    "The config_overrides keyword argument must only contain 3 top level keys: {}".format(
                        ", ".join(defaults_and_overrides_top_level_keys)
                    )
                )
            if _config_overrides:
                salt.utils.dictupdate.update(_config_overrides, config_overrides)
            else:
                _config_overrides = config_overrides.copy()

        syndic_setup_config = factory_class.default_config(
            root_dir,
            syndic_id=syndic_id,
            config_defaults=_config_defaults,
            config_overrides=_config_overrides,
            syndic_master_port=syndic_master_port,
        )

        master_config = syndic_setup_config["master"]
        self.final_master_config_tweaks(master_config)
        master_config = self.pytestconfig.hook.pytest_saltfactories_master_write_configuration(
            master_config=master_config
        )
        self.pytestconfig.hook.pytest_saltfactories_master_verify_configuration(
            master_config=master_config, username=running_username(),
        )
        master_config["pytest-master"]["master_config"] = master_of_masters_config

        minion_config = syndic_setup_config["minion"]
        self.final_minion_config_tweaks(minion_config)
        minion_config = self.pytestconfig.hook.pytest_saltfactories_minion_write_configuration(
            minion_config=minion_config
        )
        self.pytestconfig.hook.pytest_saltfactories_minion_verify_configuration(
            minion_config=minion_config, username=running_username(),
        )
        minion_config["pytest-minion"]["master_config"] = master_config

        syndic_config = syndic_setup_config["syndic"]
        self.final_syndic_config_tweaks(syndic_config)
        syndic_config = self.pytestconfig.hook.pytest_saltfactories_syndic_write_configuration(
            syndic_config=syndic_config
        )
        self.pytestconfig.hook.pytest_saltfactories_syndic_verify_configuration(
            syndic_config=syndic_config, username=running_username(),
        )
        syndic_config["pytest-syndic"]["master_config"] = master_of_masters_config
        # Just to get info about the master running along with the syndic
        syndic_config["pytest-syndic"]["syndic_master"] = master_config

        # We need the syndic master and minion running
        if syndic_id not in self.cache["masters"]:
            factory = self.get_salt_master_daemon(
                syndic_id, max_start_attempts=max_start_attempts, start_timeout=start_timeout,
            )
            factory.start()

        if syndic_id not in self.cache["minions"]:
            factory = self.get_salt_minion_daemon(
                syndic_id, max_start_attempts=max_start_attempts, start_timeout=start_timeout,
            )
            factory.start()

        return self._get_factory_class_instance(
            "salt-syndic",
            syndic_config,
            factory_class,
            "syndics",
            syndic_id,
            max_start_attempts=max_start_attempts,
            start_timeout=start_timeout,
            **extra_factory_class_kwargs,
        )

    def get_salt_proxy_minion_daemon(
        self,
        proxy_minion_id,
        master_id=None,
        config_defaults=None,
        config_overrides=None,
        max_start_attempts=3,
        start_timeout=None,
        factory_class=daemons.proxy.SaltProxyMinionFactory,
        **extra_factory_class_kwargs
    ):
        """
        Spawn a salt-proxy

        Args:
            proxy_minion_id(str):
                The proxy minion ID
            master_id(str):
                The master ID this minion will connect to.
            config_defaults(dict):
                A dictionary of default configuration to use when configuring the proxy minion
            config_overrides(dict):
                A dictionary of configuration overrides to use when configuring the proxy minion
            max_start_attempts(int):
                How many attempts should be made to start the proxy minion in case of failure to validate that
                its running
            extra_factory_class_kwargs(dict):
                Extra keyword arguments to pass to :py:class:`~saltfactories.factories.daemons.proxy.SaltProxyMinionFactory`

        Returns:
            :py:class:`~saltfactories.factories.daemons.proxy.SaltProxyMinionFactory`:
                The proxy minion process class instance
        """
        if proxy_minion_id in self.cache["proxy_minions"]:
            return self.cache["proxy_minions"][proxy_minion_id]

        master_port = None
        if master_id is not None:
            master_config = self.cache["masters"][master_id].config
            master_port = master_config.get("ret_port")

        root_dir = self._get_root_dir_for_daemon(proxy_minion_id, config_defaults=config_defaults)

        _config_defaults = self.pytestconfig.hook.pytest_saltfactories_proxy_minion_configuration_defaults(
            factories_manager=self,
            root_dir=root_dir,
            proxy_minion_id=proxy_minion_id,
            master_port=master_port,
        )
        if config_defaults:
            if _config_defaults:
                salt.utils.dictupdate.update(_config_defaults, config_defaults)
            else:
                _config_defaults = config_defaults.copy()

        _config_overrides = self.pytestconfig.hook.pytest_saltfactories_proxy_minion_configuration_overrides(
            factories_manager=self,
            root_dir=root_dir,
            proxy_minion_id=proxy_minion_id,
            config_defaults=_config_defaults,
        )
        if config_overrides:
            if _config_overrides:
                salt.utils.dictupdate.update(_config_overrides, config_overrides)
            else:
                _config_overrides = config_overrides.copy()

        proxy_minion_config = daemons.proxy.SaltProxyMinionFactory.default_config(
            root_dir,
            proxy_minion_id=proxy_minion_id,
            config_defaults=_config_defaults,
            config_overrides=_config_overrides,
            master_port=master_port,
        )
        self.final_proxy_minion_config_tweaks(proxy_minion_config)
        proxy_minion_config = self.pytestconfig.hook.pytest_saltfactories_proxy_minion_write_configuration(
            proxy_minion_config=proxy_minion_config
        )
        self.pytestconfig.hook.pytest_saltfactories_proxy_minion_verify_configuration(
            proxy_minion_config=proxy_minion_config, username=running_username(),
        )
        if master_id:
            # The in-memory proxy_minion config dictionary will hold a copy of the master config
            # in order to listen to start events so that we can confirm the proxy_minion is up, running
            # and accepting requests
            proxy_minion_config["pytest-minion"]["master_config"] = self.cache["masters"][
                master_id
            ].config

        return self._get_factory_class_instance(
            "salt-proxy",
            proxy_minion_config,
            factory_class,
            "proxy_minions",
            proxy_minion_id,
            max_start_attempts=max_start_attempts,
            start_timeout=start_timeout,
            **extra_factory_class_kwargs,
        )

    def get_salt_api_daemon(
        self,
        master_id,
        order_masters=False,
        master_of_masters_id=None,
        config_defaults=None,
        config_overrides=None,
        max_start_attempts=3,
        start_timeout=None,
        factory_class=daemons.api.SaltApiFactory,
        **extra_factory_class_kwargs
    ):
        """
        Spawn a salt-api

        Please see py:class:`~saltfactories.factories.manager.FactoriesManager.get_salt_master_daemon` for argument
        documentation.

        Returns:
            :py:class:`~saltfactories.factories.daemons.api.SaltApiFactory`:
                The salt-api process class instance
        """
        if master_id in self.cache["api"]:
            raise RuntimeError(
                "A salt-api for the master by the ID of '{}' was already spawned".format(master_id)
            )

        master = self.cache["masters"].get(master_id)
        if master is None:
            master = self.get_salt_master_daemon(
                master_id,
                order_masters=order_masters,
                master_of_masters_id=master_of_masters_id,
                config_defaults=config_defaults,
                config_overrides=config_overrides,
            )
        master_config = master.config
        return self._get_factory_class_instance(
            "salt-api",
            master_config,
            factory_class,
            "api",
            master_id,
            max_start_attempts=max_start_attempts,
            start_timeout=start_timeout,
            **extra_factory_class_kwargs,
        )

    def get_salt_cloud_cli(
        self,
        master_id,
        config_defaults=None,
        config_overrides=None,
        max_start_attempts=3,
        start_timeout=None,
        factory_class=cli.cloud.SaltCloudFactory,
        **cli_kwargs
    ):
        """
        Return a salt-cloud CLI instance

        Args:
            master_id(str):
                The master ID this salt-cloud will interact with.
            config_defaults(dict):
                A dictionary of default configuration to use when configuring the minion
            config_overrides(dict):
                A dictionary of configuration overrides to use when configuring the minion
            max_start_attempts(int):
                How many attempts should be made to start the minion in case of failure to validate that its running
            cli_kwargs(dict):
                Extra keyword arguments to pass to :py:class:`~saltfactories.factories.cli.cloud.SaltCloudFactory`

        Returns:
            :py:class:`~saltfactories.factories.cli.cloud.SaltCloudFactory`:
                The salt-cloud CLI script process class instance
        """

        if master_id in self.cache["cloud"]:
            return self.cache["cloud"][master_id]

        master = self.cache["masters"].get(master_id)
        if master is None:
            master = self.get_salt_master_daemon(
                master_id, max_start_attempts=max_start_attempts, start_timeout=start_timeout
            )
        master_config = master.config

        root_dir = pathlib.Path(master_config["root_dir"])

        _config_defaults = self.pytestconfig.hook.pytest_saltfactories_cloud_configuration_defaults(
            factories_manager=self, root_dir=root_dir, master_id=master_id,
        )
        if config_defaults:
            if _config_defaults:
                salt.utils.dictupdate.update(_config_defaults, config_defaults)
            else:
                _config_defaults = config_defaults.copy()

        _config_overrides = self.pytestconfig.hook.pytest_saltfactories_cloud_configuration_overrides(
            factories_manager=self,
            root_dir=root_dir,
            master_id=master_id,
            config_defaults=_config_defaults,
        )
        if config_overrides:
            if _config_overrides:
                salt.utils.dictupdate.update(_config_overrides, config_overrides)
            else:
                _config_overrides = config_overrides.copy()

        cloud_config = cli.cloud.SaltCloudFactory.default_config(
            root_dir,
            master_id=master_id,
            config_defaults=_config_defaults,
            config_overrides=_config_overrides,
        )
        self.final_cloud_config_tweaks(cloud_config)
        cloud_config = self.pytestconfig.hook.pytest_saltfactories_cloud_write_configuration(
            cloud_config=cloud_config
        )
        self.pytestconfig.hook.pytest_saltfactories_cloud_verify_configuration(
            cloud_config=cloud_config, username=running_username()
        )
        if master_id:
            # The in-memory minion config dictionary will hold a copy of the master config
            # in order to listen to start events so that we can confirm the minion is up, running
            # and accepting requests
            cloud_config["pytest-cloud"]["master_config"] = self.cache["masters"][master_id].config

        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            "salt-cloud",
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        factory = factory_class(cli_script_name=script_path, config=cloud_config, **cli_kwargs)
        self.cache["cloud"][master_id] = factory
        return factory

    def get_salt_client(
        self,
        master_id,
        functions_known_to_return_none=None,
        factory_class=cli.client.SaltClientFactory,
    ):
        """
        Return a local salt client object
        """
        return factory_class(
            master_config=self.cache["masters"][master_id].config.copy(),
            functions_known_to_return_none=functions_known_to_return_none,
        )

    def get_salt_cli(self, master_id, factory_class=cli.salt.SaltCliFactory, **cli_kwargs):
        """
        Return a `salt` CLI process
        """
        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            "salt",
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        return factory_class(
            cli_script_name=script_path,
            config=self.cache["masters"][master_id].config,
            **cli_kwargs,
        )

    def get_salt_call_cli(self, minion_id, factory_class=cli.call.SaltCallCliFactory, **cli_kwargs):
        """
        Return a `salt-call` CLI process
        """
        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            "salt-call",
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        try:
            return factory_class(
                cli_script_name=script_path,
                config=self.cache["minions"][minion_id].config,
                **cli_kwargs,
            )
        except KeyError:
            try:
                return factory_class(
                    cli_script_name=script_path,
                    base_script_args=["--proxyid={}".format(minion_id)],
                    config=self.cache["proxy_minions"][minion_id].config,
                    **cli_kwargs,
                )
            except KeyError:
                raise KeyError(
                    "Could not find {} in the minions or proxy minions caches".format(minion_id)
                )

    def get_salt_run_cli(self, master_id, factory_class=cli.run.SaltRunCliFactory, **cli_kwargs):
        """
        Return a `salt-run` CLI process
        """
        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            "salt-run",
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        return factory_class(
            cli_script_name=script_path,
            config=self.cache["masters"][master_id].config,
            **cli_kwargs,
        )

    def get_salt_cp_cli(self, master_id, factory_class=cli.cp.SaltCpCliFactory, **cli_kwargs):
        """
        Return a `salt-cp` CLI process
        """
        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            "salt-cp",
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        return factory_class(
            cli_script_name=script_path,
            config=self.cache["masters"][master_id].config,
            **cli_kwargs,
        )

    def get_salt_key_cli(self, master_id, factory_class=cli.key.SaltKeyCliFactory, **cli_kwargs):
        """
        Return a `salt-key` CLI process
        """
        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            "salt-key",
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        return factory_class(
            cli_script_name=script_path,
            config=self.cache["masters"][master_id].config,
            **cli_kwargs,
        )

    def get_salt_spm_cli(self, master_id, factory_class=cli.spm.SpmCliFactory, **cli_kwargs):
        """
        Return a salt `spm` CLI process
        """
        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            "spm",
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        return factory_class(
            cli_script_name=script_path,
            config=self.cache["masters"][master_id].config,
            **cli_kwargs,
        )

    def get_salt_ssh_cli(
        self,
        master_id,
        factory_class=cli.ssh.SaltSshCliFactory,
        roster_file=None,
        target_host=None,
        client_key=None,
        ssh_user=None,
        **cli_kwargs
    ):
        """
        Return a `salt-ssh` CLI process

        Args:
            roster_file(str):
                The roster file to use
            target_host(str):
                The target host address to connect to
            client_key(str):
                The path to the private ssh key to use to connect
            ssh_user(str):
                The remote username to connect as
        """
        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            "salt-ssh",
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        return factory_class(
            cli_script_name=script_path,
            config=self.cache["masters"][master_id].config,
            roster_file=roster_file,
            target_host=target_host,
            client_key=client_key,
            ssh_user=ssh_user or running_username(),
            **cli_kwargs,
        )

    def get_sshd_daemon(
        self,
        daemon_id,
        config_dir=None,
        listen_address=None,
        listen_port=None,
        sshd_config_dict=None,
        display_name=None,
        factory_class=daemons.sshd.SshdDaemonFactory,
        max_start_attempts=3,
        start_timeout=None,
        **extra_factory_class_kwargs
    ):
        """
        Start an sshd daemon

        Args:
            request(:fixture:`request`):
                The PyTest test execution request
            daemon_id(str):
                An ID so we know about the sshd server by ID
            max_start_attempts(int):
                How many attempts should be made to start the proxy minion in case of failure to validate that
                its running
            config_dir(pathlib.Path):
                The path to the sshd config directory
            listen_address(str):
                The address where the sshd server will listen to connections. Defaults to 127.0.0.1
            listen_port(int):
                The port where the sshd server will listen to connections
            sshd_config_dict(dict):
                A dictionary of key-value pairs to construct the sshd config file
            extra_factory_class_kwargs(dict):
                Extra keyword arguments to pass to :py:class:`~saltfactories.factories.daemons.sshd.SshdDaemonFactory`

        Returns:
            :py:class:`~saltfactories.factories.daemons.sshd.SshdDaemonFactory`:
                The sshd process class instance
        """
        if config_dir is None:
            config_dir = self._get_root_dir_for_daemon(daemon_id)
        try:
            config_dir = pathlib.Path(config_dir.strpath).resolve()
        except AttributeError:
            config_dir = pathlib.Path(config_dir).resolve()

        factory = factory_class(
            start_timeout=start_timeout or self.start_timeout,
            slow_stop=self.slow_stop,
            environ=self.environ,
            cwd=self.cwd,
            max_start_attempts=max_start_attempts,
            factories_manager=self,
            cli_script_name="sshd",
            display_name=display_name or "SSHD",
            config_dir=config_dir,
            listen_address=listen_address,
            listen_port=listen_port,
            sshd_config_dict=sshd_config_dict,
            **extra_factory_class_kwargs,
        )
        self.cache["factories"][daemon_id] = factory
        factory.register_after_terminate_callback(self.cache["factories"].pop, daemon_id, None)
        return factory

    def spawn_container(
        self,
        request,
        container_name,
        image_name,
        docker_client=None,
        display_name=None,
        factory_class=daemons.container.ContainerFactory,
        max_start_attempts=3,
        start_timeout=None,
        **container_run_kwargs
    ):
        """
        Start a docker container

        Args:
            request(:fixture:`request`):
                The PyTest test execution request
            container_name(str):
                The name to give the container
            image_name(str):
                The image to use
            docker_client:
                An instance of the docker client to use
            display_name(str):
                Human readable name for the factory
            factory_class:
                A factory class. (Default :py:class:`~saltfactories.factories.daemons.container.ContainerFactory`)
            max_start_attempts(int):
                How many attempts should be made to start the container in case of failure to validate that
                its running.
            start_timeout(int):
                The amount of time, in seconds, to wait, until the container is considered as not started.
            container_run_kwargs(dict):
                Extra keyword arguments to pass to :py:class:`~saltfactories.factories.daemons.container.ContainerFactory`

        Returns:
            :py:class:`~saltfactories.factories.daemons.container.ContainerFactory`:
                The factory instance
        """
        return self.start_factory(
            request,
            factory_class,
            container_name,
            name=container_name,
            image=image_name,
            docker_client=docker_client,
            display_name=display_name or container_name,
            max_start_attempts=max_start_attempts,
            start_timeout=start_timeout,
            **container_run_kwargs,
        )

    def start_factory(
        self,
        request,
        factory_class,
        factory_id,
        environ=None,
        cwd=None,
        max_start_attempts=3,
        start_timeout=None,
        **factory_class_kwargs
    ):
        """
        Start a non-salt factory
        """
        if environ is None:
            environ = self.environ
        if cwd is None:
            cwd = self.cwd
        proc = saltfactories.utils.processes.helpers.start_factory(
            factory_class,
            start_timeout=start_timeout or self.start_timeout,
            environ=environ,
            cwd=cwd,
            max_attempts=max_start_attempts,
            **factory_class_kwargs,
        )
        self.cache["factories"][factory_id] = proc
        try:
            if self.stats_processes:
                self.stats_processes[proc.get_display_name()] = psutil.Process(proc.pid)
        except AttributeError:
            # The factory does not provide the pid attribute
            pass
        request.addfinalizer(proc.terminate)
        request.addfinalizer(lambda: self.cache["factories"].pop(factory_id))
        return proc

    def _get_factory_class_instance(
        self,
        script_name,
        daemon_config,
        factory_class,
        cache_key,
        daemon_id,
        max_start_attempts,
        start_timeout,
        **factory_class_kwargs
    ):
        """
        Helper method to instantiate daemon factories
        """
        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            script_name,
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        factory = factory_class(
            config=daemon_config,
            start_timeout=start_timeout or self.start_timeout,
            slow_stop=self.slow_stop,
            environ=self.environ,
            cwd=self.cwd,
            max_start_attempts=max_start_attempts,
            event_listener=self.event_listener,
            factories_manager=self,
            cli_script_name=script_path,
            **factory_class_kwargs,
        )
        self.cache[cache_key][daemon_id] = factory
        factory.register_after_terminate_callback(self.cache[cache_key].pop, daemon_id, None)
        return factory

    def _get_root_dir_for_daemon(self, daemon_id, config_defaults=None):
        if config_defaults and "root_dir" in config_defaults:
            try:
                root_dir = pathlib.Path(config_defaults["root_dir"].strpath).resolve()
            except AttributeError:
                root_dir = pathlib.Path(config_defaults["root_dir"]).resolve()
            root_dir.mkdir(parents=True, exist_ok=True)
            return root_dir
        counter = 1
        root_dir = self.root_dir / daemon_id
        while True:
            if not root_dir.is_dir():
                break
            root_dir = self.root_dir / "{}_{}".format(daemon_id, counter)
            counter += 1
        root_dir.mkdir(parents=True, exist_ok=True)
        return root_dir

    def _handle_auth_event(self, master_id, payload):
        self.pytestconfig.hook.pytest_saltfactories_handle_key_auth_event(
            factories_manager=self,
            master_id=master_id,
            minion_id=payload["id"],
            keystate=payload["act"],
            payload=payload,
        )
