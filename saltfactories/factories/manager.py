# -*- coding: utf-8 -*-
"""
saltfactories.factories.manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Salt Factories Manager
"""
import os
import sys

import psutil
import py

try:
    import salt.utils.dictupdate
except ImportError:  # pragma: no cover
    # We need salt to test salt with saltfactories, and, when pytest is rewriting modules for proper assertion
    # reporting, we still haven't had a chance to inject the salt path into sys.modules, so we'll hit this
    # import error, but its safe to pass
    pass

import saltfactories.utils.processes.helpers
import saltfactories.utils.processes.salts as salt_factories
from saltfactories.factories import master
from saltfactories.factories import minion
from saltfactories.factories import proxy
from saltfactories.factories import syndic
from saltfactories.utils import cli_scripts
from saltfactories.utils import event_listener
from saltfactories.utils.ports import get_unused_localhost_port


class SaltFactoriesManager(object):
    """
    The :class:`SaltFactoriesManager` is responsible for configuring and spawning Salt Daemons and
    making sure that any salt CLI tools are "targetted" to the right daemon.

    It also keeps track of which daemons were started and adds their termination routines to PyTest's
    request finalization routines.

    If process statistics are enabled, it also adds the started daemons to those statistics.
    """

    def __init__(
        self,
        pytestconfig,
        root_dir,
        log_server_port=None,
        log_server_level=None,
        log_server_host=None,
        executable=None,
        code_dir=None,
        inject_coverage=False,
        inject_sitecustomize=False,
        cwd=None,
        environ=None,
        slow_stop=True,
        start_timeout=None,
        stats_processes=None,
    ):
        """

        Args:
            pytestconfig (:fixture:`pytestconfig`):
                PyTest `pytestconfig` fixture
            root_dir:
            log_server_port (int):
            log_server_level (int):
            log_server_host (str):
                The hostname/ip address of the host running the logs server. Defaults to "localhost".
            executable (str):
                The path to the python executable to use to run python CLI scripts.
                Defaults to :py:attr:`sys.executable`
            code_dir (str):
                The path to the code root directory of the project being tested. This is important for proper
                code-coverage paths.
            inject_coverage (bool):
                Inject code-coverage related code in the generated CLI scripts
            inject_sitecustomize (bool):
                Inject code in the generated CLI scripts in order for our `sitecustomise.py` to be loaded by
                subprocesses.
            cwd (str):
                The path to the current working directory
            environ(dict):
                A dictionary of `key`, `value` pairs to add to the environment.
            slow_stop(bool):
                Wether to terminate the processes by sending a :py:attr:`SIGTERM` signal or by calling
                :py:meth:`~subprocess.Popen.terminate` on the sub-procecess.
                When code coverage is enabled, one will want `slow_stop` set to `True` so that coverage data
                can be written down to disk.
            start_timeout(int):
                The amount of time, in seconds, to wait, until a subprocess is considered as not started.
            stats_processes (:py:class:`~collections.OrderedDict`):
                This will be an `OrderedDict` instantiated on the :py:func:`~_pytest.hookspec.pytest_sessionstart`
                hook accessible at `stats_processes` on the `session` attribute of the :fixture:`request`.
        """
        self.pytestconfig = pytestconfig
        self.stats_processes = stats_processes
        self.root_dir = root_dir
        self.log_server_port = log_server_port or get_unused_localhost_port()
        self.log_server_level = log_server_level or "error"
        self.log_server_host = log_server_host or "localhost"
        self.executable = executable or sys.executable
        self.code_dir = code_dir
        self.inject_coverage = inject_coverage
        self.inject_sitecustomize = inject_sitecustomize
        self.cwd = cwd
        self.environ = environ
        self.slow_stop = slow_stop
        if start_timeout is None:
            if not sys.platform.startswith("win"):
                start_timeout = 30
            else:
                # Windows is just slower
                start_timeout = 120
        self.start_timeout = start_timeout
        self.scripts_dir = root_dir.join("scripts").ensure(dir=True).strpath
        self.configs = {"minions": {}, "masters": {}}
        self.masters = {}
        self.minions = {}
        self.cache = {
            "configs": {"masters": {}, "minions": {}, "syndics": {}, "proxy_minions": {}},
            "masters": {},
            "minions": {},
            "syndics": {},
            "proxy_minions": {},
            "daemons": {},
        }
        self.event_listener = event_listener.EventListener(
            auth_events_callback=self._handle_auth_event
        )
        self.event_listener.start()

    @staticmethod
    def get_running_username():
        """
        Returns the current username
        """
        try:
            return SaltFactoriesManager.get_running_username.__username__
        except AttributeError:
            if saltfactories.IS_WINDOWS:
                import win32api

                SaltFactoriesManager.get_running_username.__username__ = win32api.GetUserName()
            else:
                import pwd

                SaltFactoriesManager.get_running_username.__username__ = pwd.getpwuid(
                    os.getuid()
                ).pw_name
        return SaltFactoriesManager.get_running_username.__username__

    @staticmethod
    def get_salt_log_handlers_path():
        """
        Returns the path to the Salt log handler this plugin provides
        """
        return os.path.join(saltfactories.CODE_ROOT_DIR, "utils", "salt", "log_handlers")

    @staticmethod
    def get_salt_engines_path():
        """
        Returns the path to the Salt engine this plugin provides
        """
        return os.path.join(saltfactories.CODE_ROOT_DIR, "utils", "salt", "engines")

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

    def final_common_config_tweaks(self, config, role):
        config.setdefault("engines", [])
        if "pytest" not in config["engines"]:
            config["engines"].append("pytest")

        if "engines_dirs" not in config:
            config["engines_dirs"] = []
        config["engines_dirs"].insert(0, SaltFactoriesManager.get_salt_engines_path())
        config.setdefault("user", SaltFactoriesManager.get_running_username())
        if not config["user"]:
            # If this value is empty, None, False, just remove it
            config.pop("user")
        if "log_forwarding_consumer" not in config:
            # Still using old logging, let's add our custom log handler
            if "log_handlers_dirs" not in config:
                config["log_handlers_dirs"] = []
            config["log_handlers_dirs"].insert(0, SaltFactoriesManager.get_salt_log_handlers_path())

        pytest_key = "pytest-{}".format(role)
        if pytest_key not in config:
            config[pytest_key] = {}

        pytest_config = config[pytest_key]
        if "log" not in pytest_config:
            pytest_config["log"] = {}

        log_config = pytest_config["log"]
        log_config["host"] = self.log_server_host
        log_config["port"] = self.log_server_port
        log_config["level"] = self.log_server_level

    def configure_master(
        self,
        request,
        master_id,
        order_masters=False,
        master_of_masters_id=None,
        config_defaults=None,
        config_overrides=None,
    ):
        """
        Configure a salt-master

        Args:
            request(:fixture:`request`):
                The PyTest test execution request
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

        Returns:
            dict: The master configuring dictionary
        """
        if master_id in self.cache["configs"]["masters"]:
            return self.cache["configs"]["masters"][master_id]

        root_dir = self._get_root_dir_for_daemon(master_id, config_defaults=config_defaults)

        _config_defaults = self.pytestconfig.hook.pytest_saltfactories_master_configuration_defaults(
            request=request,
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
            request=request,
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
            master_of_masters_config = self.cache["configs"]["masters"].get(master_of_masters_id)
            if master_of_masters_config is None:
                raise RuntimeError("No config found for {}".format(master_of_masters_id))
            if config_overrides is None:
                config_overrides = {}
            config_overrides["syndic_master"] = master_of_masters_config["interface"]
            config_overrides["syndic_master_port"] = master_of_masters_config["ret_port"]

        master_config = master.MasterFactory.default_config(
            root_dir,
            master_id=master_id,
            config_defaults=_config_defaults,
            config_overrides=_config_overrides,
            order_masters=order_masters,
        )
        self.final_master_config_tweaks(master_config)
        master_config = self.pytestconfig.hook.pytest_saltfactories_master_write_configuration(
            request=request, master_config=master_config
        )
        self.pytestconfig.hook.pytest_saltfactories_master_verify_configuration(
            request=request,
            master_config=master_config,
            username=SaltFactoriesManager.get_running_username(),
        )
        self.cache["configs"]["masters"][master_id] = master_config
        request.addfinalizer(lambda: self.cache["configs"]["masters"].pop(master_id))
        return master_config

    def spawn_master(
        self,
        request,
        master_id,
        order_masters=False,
        master_of_masters_id=None,
        config_defaults=None,
        config_overrides=None,
        max_start_attempts=3,
        daemon_class=salt_factories.SaltMaster,
        **extra_daemon_class_kwargs
    ):
        """
        Spawn a salt-master

        Args:
            request(:fixture:`request`):
                The PyTest test execution request
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
            extra_daemon_class_kwargs(dict):
                Extra keyword arguments to pass to :py:class:`~saltfactories.utils.processes.salts.SaltMaster`

        Returns:
            :py:class:`~saltfactories.utils.processes.salts.SaltMaster`:
                The master process class instance
        """
        if master_id in self.cache["masters"]:
            raise RuntimeError("A master by the ID of '{}' was already spawned".format(master_id))

        master_config = self.cache["configs"]["masters"].get(master_id)
        if master_config is None:
            master_config = self.configure_master(
                request,
                master_id,
                order_masters=order_masters,
                master_of_masters_id=master_of_masters_id,
                config_defaults=config_defaults,
                config_overrides=config_overrides,
            )

        return self._start_daemon(
            request,
            "salt-master",
            master_config,
            daemon_class,
            "masters",
            master_id,
            max_start_attempts=max_start_attempts,
            **extra_daemon_class_kwargs,
        )

    def configure_minion(
        self, request, minion_id, master_id=None, config_defaults=None, config_overrides=None
    ):
        """
        Configure a salt-minion

        Args:
            request(:fixture:`request`):
                The PyTest test execution request
            minion_id(str):
                The minion ID
            master_id(str):
                The master ID this minion will connect to.
            config_defaults(dict):
                A dictionary of default configuration to use when configuring the minion
            config_overrides(dict):
                A dictionary of configuration overrides to use when configuring the minion

        Returns:
            dict: The minion configuration dictionary

        """
        if minion_id in self.cache["configs"]["minions"]:
            return self.cache["configs"]["minions"][minion_id]

        root_dir = self._get_root_dir_for_daemon(minion_id, config_defaults=config_defaults)

        master_port = None
        if master_id is not None:
            master_config = self.cache["configs"]["masters"][master_id]
            master_port = master_config.get("ret_port")

        _config_defaults = self.pytestconfig.hook.pytest_saltfactories_minion_configuration_defaults(
            request=request,
            factories_manager=self,
            root_dir=root_dir,
            minion_id=minion_id,
            master_port=master_port,
        )
        if config_defaults:
            if _config_defaults:
                salt.utils.dictupdate.update(_config_defaults, config_defaults)
            else:
                _config_defaults = config_defaults.copy()

        _config_overrides = self.pytestconfig.hook.pytest_saltfactories_minion_configuration_overrides(
            request=request,
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

        minion_config = minion.MinionFactory.default_config(
            root_dir,
            minion_id=minion_id,
            config_defaults=_config_defaults,
            config_overrides=_config_overrides,
            master_port=master_port,
        )
        self.final_minion_config_tweaks(minion_config)
        minion_config = self.pytestconfig.hook.pytest_saltfactories_minion_write_configuration(
            request=request, minion_config=minion_config
        )
        self.pytestconfig.hook.pytest_saltfactories_minion_verify_configuration(
            request=request,
            minion_config=minion_config,
            username=SaltFactoriesManager.get_running_username(),
        )
        if master_id:
            # The in-memory minion config dictionary will hold a copy of the master config
            # in order to listen to start events so that we can confirm the minion is up, running
            # and accepting requests
            minion_config["pytest-minion"]["master_config"] = self.cache["configs"]["masters"][
                master_id
            ]
        self.cache["configs"]["minions"][minion_id] = minion_config
        request.addfinalizer(lambda: self.cache["configs"]["minions"].pop(minion_id))
        return minion_config

    def spawn_minion(
        self,
        request,
        minion_id,
        master_id=None,
        config_defaults=None,
        config_overrides=None,
        max_start_attempts=3,
        daemon_class=salt_factories.SaltMinion,
        **extra_daemon_class_kwargs
    ):
        """
        Spawn a salt-minion

        Args:
            request(:fixture:`request`):
                The PyTest test execution request
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
            extra_daemon_class_kwargs(dict):
                Extra keyword arguments to pass to :py:class:`~saltfactories.utils.processes.salts.SaltMinion`

        Returns:
            :py:class:`~saltfactories.utils.processes.salts.SaltMinion`:
                The minion process class instance
        """
        if minion_id in self.cache["minions"]:
            raise RuntimeError("A minion by the ID of '{}' was already spawned".format(minion_id))

        minion_config = self.cache["configs"]["minions"].get(minion_id)
        if minion_config is None:
            minion_config = self.configure_minion(
                request,
                minion_id,
                master_id=master_id,
                config_defaults=config_defaults,
                config_overrides=config_overrides,
            )

        return self._start_daemon(
            request,
            "salt-minion",
            minion_config,
            daemon_class,
            "minions",
            minion_id,
            max_start_attempts=max_start_attempts,
            **extra_daemon_class_kwargs,
        )

    def configure_syndic(
        self,
        request,
        syndic_id,
        master_of_masters_id=None,
        config_defaults=None,
        config_overrides=None,
    ):
        """
        Configure a salt-syndic.

        In order for the syndic to be reactive, it actually needs three(3) daemons running, `salt-master`,
        `salt-minion` and `salt-syndic`.

        Args:
            request(:fixture:`request`):
                The PyTest test execution request
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

        Returns:
            dict: The syndic configuring dictionary
        """
        if syndic_id in self.cache["configs"]["syndics"]:
            return self.cache["configs"]["syndics"][syndic_id]
        elif syndic_id in self.cache["configs"]["masters"]:
            raise RuntimeError(
                "A master by the ID of '{}' was already configured".format(syndic_id)
            )
        elif syndic_id in self.cache["configs"]["minions"]:
            raise RuntimeError(
                "A minion by the ID of '{}' was already configured".format(syndic_id)
            )

        master_of_masters_config = self.cache["configs"]["masters"].get(master_of_masters_id)
        if master_of_masters_config is None and master_of_masters_id:
            master_of_masters_config = self.configure_master(
                request, master_of_masters_id, order_masters=True
            )

        syndic_master_port = master_of_masters_config["ret_port"]

        root_dir = self._get_root_dir_for_daemon(
            syndic_id, config_defaults=config_defaults.get("syndic") if config_defaults else None
        )

        defaults_and_overrides_top_level_keys = {"master", "minion", "syndic"}

        _config_defaults = self.pytestconfig.hook.pytest_saltfactories_syndic_configuration_defaults(
            request=request,
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
            request=request,
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

        syndic_setup_config = syndic.SyndicFactory.default_config(
            root_dir,
            syndic_id=syndic_id,
            config_defaults=_config_defaults,
            config_overrides=_config_overrides,
            syndic_master_port=syndic_master_port,
        )

        master_config = syndic_setup_config["master"]
        self.final_master_config_tweaks(master_config)
        master_config = self.pytestconfig.hook.pytest_saltfactories_master_write_configuration(
            request=request, master_config=master_config
        )
        self.pytestconfig.hook.pytest_saltfactories_master_verify_configuration(
            request=request,
            master_config=master_config,
            username=SaltFactoriesManager.get_running_username(),
        )
        master_config["pytest-master"]["master_config"] = master_of_masters_config
        self.cache["configs"]["masters"][syndic_id] = master_config
        request.addfinalizer(lambda: self.cache["configs"]["masters"].pop(syndic_id))

        minion_config = syndic_setup_config["minion"]
        self.final_minion_config_tweaks(minion_config)
        minion_config = self.pytestconfig.hook.pytest_saltfactories_minion_write_configuration(
            request=request, minion_config=minion_config
        )
        self.pytestconfig.hook.pytest_saltfactories_minion_verify_configuration(
            request=request,
            minion_config=minion_config,
            username=SaltFactoriesManager.get_running_username(),
        )
        minion_config["pytest-minion"]["master_config"] = master_config
        self.cache["configs"]["minions"][syndic_id] = minion_config
        request.addfinalizer(lambda: self.cache["configs"]["minions"].pop(syndic_id))

        syndic_config = syndic_setup_config["syndic"]
        self.final_syndic_config_tweaks(syndic_config)
        syndic_config = self.pytestconfig.hook.pytest_saltfactories_syndic_write_configuration(
            request=request, syndic_config=syndic_config
        )
        self.pytestconfig.hook.pytest_saltfactories_syndic_verify_configuration(
            request=request,
            syndic_config=syndic_config,
            username=SaltFactoriesManager.get_running_username(),
        )
        syndic_config["pytest-syndic"]["master_config"] = master_of_masters_config
        # Just to get info about the master running along with the syndic
        syndic_config["pytest-syndic"]["syndic_master"] = master_config
        self.cache["configs"]["syndics"][syndic_id] = syndic_config
        request.addfinalizer(lambda: self.cache["configs"]["syndics"].pop(syndic_id))
        return syndic_config

    def spawn_syndic(
        self,
        request,
        syndic_id,
        master_of_masters_id=None,
        config_defaults=None,
        config_overrides=None,
        max_start_attempts=3,
        daemon_class=salt_factories.SaltSyndic,
        **extra_daemon_class_kwargs
    ):
        """
        Spawn a salt-syndic

        Args:
            request(:fixture:`request`):
                The PyTest test execution request
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
            extra_daemon_class_kwargs(dict):
                Extra keyword arguments to pass to :py:class:`~saltfactories.utils.processes.salts.SaltSyndic`

        Returns:
            :py:class:`~saltfactories.utils.processes.salts.SaltSyndic`:
                The syndic process class instance
        """
        if syndic_id in self.cache["syndics"]:
            raise RuntimeError("A syndic by the ID of '{}' was already spawned".format(syndic_id))

        syndic_config = self.cache["configs"]["syndics"].get(syndic_id)
        if syndic_config is None:
            syndic_config = self.configure_syndic(
                request,
                syndic_id,
                master_of_masters_id=master_of_masters_id,
                config_defaults=config_defaults,
                config_overrides=config_overrides,
            )

        # We need the syndic master and minion running
        if syndic_id not in self.cache["masters"]:
            self.spawn_master(
                request, syndic_id, max_start_attempts=max_start_attempts,
            )

        if syndic_id not in self.cache["minions"]:
            self.spawn_minion(
                request, syndic_id, max_start_attempts=max_start_attempts,
            )

        return self._start_daemon(
            request,
            "salt-syndic",
            syndic_config,
            daemon_class,
            "syndics",
            syndic_id,
            max_start_attempts=max_start_attempts,
            **extra_daemon_class_kwargs,
        )

    def configure_proxy_minion(
        self, request, proxy_minion_id, master_id=None, config_defaults=None, config_overrides=None
    ):
        """
        Configure a salt-proxy

        Args:
            request(:fixture:`request`):
                The PyTest test execution request
            proxy_minion_id(str):
                The proxy minion ID
            master_id(str):
                The master ID this minion will connect to.
            config_defaults(dict):
                A dictionary of default configuration to use when configuring the proxy minion
            config_overrides(dict):
                A dictionary of configuration overrides to use when configuring the proxy minion

        Returns:
            dict: The proxy minion configuration dictionary
        """
        if proxy_minion_id in self.cache["configs"]["proxy_minions"]:
            return self.cache["configs"]["proxy_minions"][proxy_minion_id]

        master_port = None
        if master_id is not None:
            master_config = self.cache["configs"]["masters"][master_id]
            master_port = master_config.get("ret_port")

        root_dir = self._get_root_dir_for_daemon(proxy_minion_id, config_defaults=config_defaults)

        _config_defaults = self.pytestconfig.hook.pytest_saltfactories_proxy_minion_configuration_defaults(
            request=request,
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
            request=request,
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

        proxy_minion_config = proxy.ProxyMinionFactory.default_config(
            root_dir,
            proxy_minion_id=proxy_minion_id,
            config_defaults=_config_defaults,
            config_overrides=_config_overrides,
            master_port=master_port,
        )
        self.final_proxy_minion_config_tweaks(proxy_minion_config)
        proxy_minion_config = self.pytestconfig.hook.pytest_saltfactories_proxy_minion_write_configuration(
            request=request, proxy_minion_config=proxy_minion_config
        )
        self.pytestconfig.hook.pytest_saltfactories_proxy_minion_verify_configuration(
            request=request,
            proxy_minion_config=proxy_minion_config,
            username=SaltFactoriesManager.get_running_username(),
        )
        if master_id:
            # The in-memory proxy_minion config dictionary will hold a copy of the master config
            # in order to listen to start events so that we can confirm the proxy_minion is up, running
            # and accepting requests
            proxy_minion_config["pytest-minion"]["master_config"] = self.cache["configs"][
                "masters"
            ][master_id]
        self.cache["configs"]["proxy_minions"][proxy_minion_id] = proxy_minion_config
        request.addfinalizer(lambda: self.cache["configs"]["proxy_minions"].pop(proxy_minion_id))
        return proxy_minion_config

    def spawn_proxy_minion(
        self,
        request,
        proxy_minion_id,
        master_id=None,
        config_defaults=None,
        config_overrides=None,
        max_start_attempts=3,
        daemon_class=salt_factories.SaltProxyMinion,
        **extra_daemon_class_kwargs
    ):
        """
        Spawn a salt-proxy

        Args:
            request(:fixture:`request`):
                The PyTest test execution request
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
            extra_daemon_class_kwargs(dict):
                Extra keyword arguments to pass to :py:class:`~saltfactories.utils.processes.salts.SaltProxyMinion`

        Returns:
            :py:class:`~saltfactories.utils.processes.salts.SaltProxyMinion`:
                The proxy minion process class instance
        """
        if proxy_minion_id in self.cache["proxy_minions"]:
            raise RuntimeError(
                "A proxy_minion by the ID of '{}' was already spawned".format(proxy_minion_id)
            )

        proxy_minion_config = self.cache["configs"]["proxy_minions"].get(proxy_minion_id)
        if proxy_minion_config is None:
            proxy_minion_config = self.configure_proxy_minion(
                request,
                proxy_minion_id,
                master_id=master_id,
                config_defaults=config_defaults,
                config_overrides=config_overrides,
            )

        return self._start_daemon(
            request,
            "salt-proxy",
            proxy_minion_config,
            daemon_class,
            "proxy_minions",
            proxy_minion_id,
            max_start_attempts=max_start_attempts,
            **extra_daemon_class_kwargs,
        )

    def get_salt_client(
        self, master_id, functions_known_to_return_none=None, cli_class=salt_factories.SaltClient
    ):
        """
        Return a local salt client object
        """
        return cli_class(
            master_config=self.cache["configs"]["masters"][master_id].copy(),
            functions_known_to_return_none=functions_known_to_return_none,
        )

    def get_salt_cli(self, master_id, cli_class=salt_factories.SaltCLI, **cli_kwargs):
        """
        Return a `salt` CLI process
        """
        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            "salt",
            executable=self.executable,
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        return cli_class(
            script_path, config=self.cache["configs"]["masters"][master_id], **cli_kwargs
        )

    def get_salt_call_cli(self, minion_id, cli_class=salt_factories.SaltCallCLI, **cli_kwargs):
        """
        Return a `salt-call` CLI process
        """
        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            "salt-call",
            executable=self.executable,
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        try:
            return cli_class(
                script_path, config=self.cache["configs"]["minions"][minion_id], **cli_kwargs
            )
        except KeyError:
            try:
                return cli_class(
                    script_path,
                    base_script_args=["--proxyid={}".format(minion_id)],
                    config=self.cache["proxy_minions"][minion_id].config,
                    **cli_kwargs,
                )
            except KeyError:
                raise KeyError(
                    "Could not find {} in the minions or proxy minions caches".format(minion_id)
                )

    def get_salt_run_cli(self, master_id, cli_class=salt_factories.SaltRunCLI, **cli_kwargs):
        """
        Return a `salt-run` CLI process
        """
        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            "salt-run",
            executable=self.executable,
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        return cli_class(
            script_path, config=self.cache["configs"]["masters"][master_id], **cli_kwargs
        )

    def get_salt_cp_cli(self, master_id, cli_class=salt_factories.SaltCpCLI, **cli_kwargs):
        """
        Return a `salt-cp` CLI process
        """
        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            "salt-cp",
            executable=self.executable,
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        return cli_class(
            script_path, config=self.cache["configs"]["masters"][master_id], **cli_kwargs
        )

    def get_salt_key_cli(self, master_id, cli_class=salt_factories.SaltKeyCLI, **cli_kwargs):
        """
        Return a `salt-key` CLI process
        """
        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            "salt-key",
            executable=self.executable,
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        return cli_class(
            script_path, config=self.cache["configs"]["masters"][master_id], **cli_kwargs
        )

    def spawn_daemon(
        self,
        request,
        script_name,
        daemon_class,
        daemon_id,
        environ=None,
        cwd=None,
        slow_stop=None,
        max_start_attempts=3,
        **extra_daemon_class_kwargs
    ):
        """
        Start a non-salt daemon
        """
        if environ is None:
            environ = self.environ
        if cwd is None:
            cwd = self.cwd
        if slow_stop is None:
            slow_stop = False
        proc = saltfactories.utils.processes.helpers.start_daemon(
            script_name,
            daemon_class,
            start_timeout=self.start_timeout,
            slow_stop=slow_stop,
            environ=environ,
            cwd=cwd,
            max_attempts=max_start_attempts,
            **extra_daemon_class_kwargs,
        )
        self.cache["daemons"][daemon_id] = proc
        if self.stats_processes:
            self.stats_processes[proc.get_display_name()] = psutil.Process(proc.pid)
        request.addfinalizer(proc.terminate)
        request.addfinalizer(lambda: self.cache["daemons"].pop(daemon_id))
        return proc

    def _start_daemon(
        self,
        request,
        script_name,
        daemon_config,
        daemon_class,
        cache_key,
        daemon_id,
        max_start_attempts=3,
        **extra_daemon_class_kwargs
    ):
        """
        Helper method to start daemons
        """
        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            script_name,
            executable=self.executable,
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        proc = saltfactories.utils.processes.helpers.start_daemon(
            script_path,
            daemon_class,
            config=daemon_config,
            start_timeout=self.start_timeout,
            slow_stop=self.slow_stop,
            environ=self.environ,
            cwd=self.cwd,
            max_attempts=max_start_attempts,
            event_listener=self.event_listener,
            salt_factories=self,
            **extra_daemon_class_kwargs,
        )
        self.cache[cache_key][daemon_id] = proc
        if self.stats_processes:
            self.stats_processes[proc.get_display_name()] = psutil.Process(proc.pid)
        request.addfinalizer(proc.terminate)
        request.addfinalizer(lambda: self.cache[cache_key].pop(daemon_id))
        return proc

    def _get_root_dir_for_daemon(self, daemon_id, config_defaults=None):
        if config_defaults and "root_dir" in config_defaults:
            return py.path.local(config_defaults["root_dir"]).ensure(dir=True)
        counter = 1
        root_dir = self.root_dir.join(daemon_id)
        while True:
            if not root_dir.check(dir=True):
                break
            root_dir = self.root_dir.join("{}_{}".format(daemon_id, counter))
            counter += 1
        root_dir.ensure(dir=True)
        return root_dir

    def _handle_auth_event(self, master_id, payload):
        self.pytestconfig.hook.pytest_saltfactories_handle_key_auth_event(
            factories_manager=self,
            master_id=master_id,
            minion_id=payload["id"],
            keystate=payload["act"],
            payload=payload,
        )
