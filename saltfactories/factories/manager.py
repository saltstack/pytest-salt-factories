# -*- coding: utf-8 -*-
"""
saltfactories.factories.manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Salt Factories Manager
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import os
import sys

import psutil

import saltfactories.utils.processes.helpers
import saltfactories.utils.processes.salts as salt_factories
from saltfactories.factories import master
from saltfactories.factories import minion
from saltfactories.factories import proxy
from saltfactories.factories import syndic
from saltfactories.utils import cli_scripts
from saltfactories.utils import event_listener


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
        log_server_port,
        log_server_level,
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
            executable (str) :
                The path to the python executable to use to run python CLI scripts.
                Defaults to :py:attr:`sys.executable`
            code_dir (str):
                The path to the code root directory of the project being tested. This is important for proper
                code-coverage paths.
            inject_coverage (bool):
                Inject code-coverage related code in the generated CLI scripts
            inject_sitecustomize (bool):
                Inject code in the generated CLI scripts in order for our `sitecustumise.py` to be loaded by
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
        self.log_server_port = log_server_port
        self.log_server_level = log_server_level
        self.executable = executable or sys.executable
        self.code_dir = code_dir
        self.inject_coverage = inject_coverage
        self.inject_sitecustomize = inject_sitecustomize
        self.cwd = cwd
        self.environ = environ
        self.slow_stop = slow_stop
        if start_timeout is None:
            start_timeout = 30
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
        self.event_listener = event_listener.EventListener()
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
        config["user"] = SaltFactoriesManager.get_running_username()
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
        log_config["host"] = "localhost"
        log_config["port"] = self.log_server_port
        log_config["level"] = self.log_server_level

    def configure_minion(self, request, minion_id, master_id=None):
        """
        Configure a salt-minion
        """
        if minion_id in self.cache["configs"]["minions"]:
            return self.cache["configs"]["minions"][minion_id]

        root_dir = self._get_root_dir_for_daemon(minion_id)

        master_port = None
        if master_id is not None:
            master_config = self.cache["configs"]["masters"][master_id]
            master_port = master_config.get("ret_port")
        default_options = self.pytestconfig.hook.pytest_saltfactories_generate_default_minion_configuration(
            request=request,
            factories_manager=self,
            root_dir=root_dir,
            minion_id=minion_id,
            master_port=master_port,
        )
        config_overrides = self.pytestconfig.hook.pytest_saltfactories_minion_configuration_overrides(
            request=request,
            factories_manager=self,
            root_dir=root_dir,
            minion_id=minion_id,
            default_options=default_options,
        )
        minion_config = minion.MinionFactory.default_config(
            root_dir,
            minion_id=minion_id,
            default_options=default_options,
            config_overrides=config_overrides,
            master_port=master_port,
        )
        self.final_minion_config_tweaks(minion_config)
        minion_config = self.pytestconfig.hook.pytest_saltfactories_write_minion_configuration(
            request=request, minion_config=minion_config
        )
        self.pytestconfig.hook.pytest_saltfactories_verify_minion_configuration(
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

    def spawn_minion(self, request, minion_id, master_id=None):
        """
        Spawn a salt-minion
        """
        if minion_id in self.cache["minions"]:
            raise RuntimeError("A minion by the ID of '{}' was already spawned".format(minion_id))

        minion_config = self.cache["configs"]["minions"].get(minion_id)
        if minion_config is None:
            minion_config = self.configure_minion(request, minion_id, master_id=master_id)

        return self._start_daemon(
            request, "salt-minion", minion_config, salt_factories.SaltMinion, "minions", minion_id
        )

    def configure_master(self, request, master_id, order_masters=False, master_of_masters_id=None):
        """
        Configure a salt-master
        """
        if master_id in self.cache["configs"]["masters"]:
            return self.cache["configs"]["masters"][master_id]

        root_dir = self._get_root_dir_for_daemon(master_id)

        default_options = self.pytestconfig.hook.pytest_saltfactories_generate_default_master_configuration(
            request=request,
            factories_manager=self,
            root_dir=root_dir,
            master_id=master_id,
            order_masters=order_masters,
        )
        config_overrides = self.pytestconfig.hook.pytest_saltfactories_master_configuration_overrides(
            request=request,
            factories_manager=self,
            root_dir=root_dir,
            master_id=master_id,
            default_options=default_options,
            order_masters=order_masters,
        )

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
            default_options=default_options,
            config_overrides=config_overrides,
            order_masters=order_masters,
        )
        self.final_master_config_tweaks(master_config)
        master_config = self.pytestconfig.hook.pytest_saltfactories_write_master_configuration(
            request=request, master_config=master_config
        )
        self.pytestconfig.hook.pytest_saltfactories_verify_master_configuration(
            request=request,
            master_config=master_config,
            username=SaltFactoriesManager.get_running_username(),
        )
        self.cache["configs"]["masters"][master_id] = master_config
        request.addfinalizer(lambda: self.cache["configs"]["masters"].pop(master_id))
        return master_config

    def spawn_master(
        self, request, master_id, order_masters=False, master_of_masters_id=None,
    ):
        """
        Spawn a salt-master
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
            )

        return self._start_daemon(
            request, "salt-master", master_config, salt_factories.SaltMaster, "masters", master_id
        )

    def configure_syndic(self, request, syndic_id, master_of_masters_id=None):
        """
        Configure a salt-syndic.

        In order for the syndic to be reactive, it actually needs three(3) daemons running, `salt-master`,
        `salt-minion` and `salt-syndic`.

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

        root_dir = self._get_root_dir_for_daemon(syndic_id)

        default_options = self.pytestconfig.hook.pytest_saltfactories_generate_default_syndic_configuration(
            request=request,
            factories_manager=self,
            root_dir=root_dir,
            syndic_id=syndic_id,
            syndic_master_port=syndic_master_port,
        )

        config_overrides = self.pytestconfig.hook.pytest_saltfactories_syndic_configuration_overrides(
            request=request,
            factories_manager=self,
            root_dir=root_dir,
            syndic_id=syndic_id,
            default_options=default_options,
        )

        syndic_setup_config = syndic.SyndicFactory.default_config(
            root_dir,
            syndic_id=syndic_id,
            default_options=default_options,
            config_overrides=config_overrides,
            syndic_master_port=syndic_master_port,
        )

        master_config = syndic_setup_config["master"]
        self.final_master_config_tweaks(master_config)
        master_config = self.pytestconfig.hook.pytest_saltfactories_write_master_configuration(
            request=request, master_config=master_config
        )
        self.pytestconfig.hook.pytest_saltfactories_verify_master_configuration(
            request=request,
            master_config=master_config,
            username=SaltFactoriesManager.get_running_username(),
        )
        master_config["pytest-master"]["master_config"] = master_of_masters_config
        self.cache["configs"]["masters"][syndic_id] = master_config
        request.addfinalizer(lambda: self.cache["configs"]["masters"].pop(syndic_id))

        minion_config = syndic_setup_config["minion"]
        self.final_minion_config_tweaks(minion_config)
        minion_config = self.pytestconfig.hook.pytest_saltfactories_write_minion_configuration(
            request=request, minion_config=minion_config
        )
        self.pytestconfig.hook.pytest_saltfactories_verify_minion_configuration(
            request=request,
            minion_config=minion_config,
            username=SaltFactoriesManager.get_running_username(),
        )
        minion_config["pytest-minion"]["master_config"] = master_config
        self.cache["configs"]["minions"][syndic_id] = minion_config
        request.addfinalizer(lambda: self.cache["configs"]["minions"].pop(syndic_id))

        syndic_config = syndic_setup_config["syndic"]
        self.final_syndic_config_tweaks(syndic_config)
        syndic_config = self.pytestconfig.hook.pytest_saltfactories_write_syndic_configuration(
            request=request, syndic_config=syndic_config
        )
        self.pytestconfig.hook.pytest_saltfactories_verify_syndic_configuration(
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

    def spawn_syndic(self, request, syndic_id, master_of_masters_id=None):
        """
        Spawn a salt-syndic
        """
        if syndic_id in self.cache["syndics"]:
            raise RuntimeError("A syndic by the ID of '{}' was already spawned".format(syndic_id))

        syndic_config = self.cache["configs"]["syndics"].get(syndic_id)
        if syndic_config is None:
            syndic_config = self.configure_syndic(
                request, syndic_id, master_of_masters_id=master_of_masters_id
            )

        # We need the syndic master and minion running
        if syndic_id not in self.cache["masters"]:
            self.spawn_master(request, syndic_id)

        if syndic_id not in self.cache["minions"]:
            self.spawn_minion(request, syndic_id)

        return self._start_daemon(
            request, "salt-syndic", syndic_config, salt_factories.SaltSyndic, "syndics", syndic_id
        )

    def configure_proxy_minion(self, request, proxy_minion_id, master_id=None):
        """
        Configure a salt-proxy
        """
        if proxy_minion_id in self.cache["configs"]["proxy_minions"]:
            return self.cache["configs"]["proxy_minions"][proxy_minion_id]

        master_port = None
        if master_id is not None:
            master_config = self.cache["configs"]["masters"][master_id]
            master_port = master_config.get("ret_port")

        root_dir = self._get_root_dir_for_daemon(proxy_minion_id)

        default_options = self.pytestconfig.hook.pytest_saltfactories_generate_default_proxy_minion_configuration(
            request=request,
            factories_manager=self,
            root_dir=root_dir,
            proxy_minion_id=proxy_minion_id,
            master_port=master_port,
        )
        config_overrides = self.pytestconfig.hook.pytest_saltfactories_proxy_minion_configuration_overrides(
            request=request,
            factories_manager=self,
            root_dir=root_dir,
            proxy_minion_id=proxy_minion_id,
            default_options=default_options,
        )
        proxy_minion_config = proxy.ProxyMinionFactory.default_config(
            root_dir,
            proxy_minion_id=proxy_minion_id,
            default_options=default_options,
            config_overrides=config_overrides,
            master_port=master_port,
        )
        self.final_proxy_minion_config_tweaks(proxy_minion_config)
        proxy_minion_config = self.pytestconfig.hook.pytest_saltfactories_write_proxy_minion_configuration(
            request=request, proxy_minion_config=proxy_minion_config
        )
        self.pytestconfig.hook.pytest_saltfactories_verify_proxy_minion_configuration(
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

    def spawn_proxy_minion(self, request, proxy_minion_id, master_id=None):
        """
        Spawn a salt-proxy
        """
        if proxy_minion_id in self.cache["proxy_minions"]:
            raise RuntimeError(
                "A proxy_minion by the ID of '{}' was already spawned".format(proxy_minion_id)
            )

        proxy_minion_config = self.cache["configs"]["proxy_minions"].get(proxy_minion_id)
        if proxy_minion_config is None:
            proxy_minion_config = self.configure_proxy_minion(
                request, proxy_minion_id, master_id=master_id
            )

        return self._start_daemon(
            request,
            "salt-proxy",
            proxy_minion_config,
            salt_factories.SaltProxyMinion,
            "proxy_minions",
            proxy_minion_id,
        )

    def get_salt_cli(self, request, master_id, **cli_kwargs):
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
        return salt_factories.SaltCLI(
            script_path, config=self.cache["masters"][master_id].config, **cli_kwargs
        )

    def get_salt_call_cli(self, request, minion_id, **cli_kwargs):
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
            return salt_factories.SaltCallCLI(
                script_path, config=self.cache["minions"][minion_id].config, **cli_kwargs
            )
        except KeyError:
            try:
                return salt_factories.SaltCallCLI(
                    script_path,
                    base_script_args=["--proxyid={}".format(minion_id)],
                    config=self.cache["proxy_minions"][minion_id].config,
                    **cli_kwargs
                )
            except KeyError:
                raise KeyError(
                    "Could not find {} in the minions or proxy minions caches".format(minion_id)
                )

    def get_salt_run(self, request, master_id, **cli_kwargs):
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
        return salt_factories.SaltRunCLI(
            script_path, config=self.cache["masters"][master_id].config, **cli_kwargs
        )

    def get_salt_cp(self, request, master_id, **cli_kwargs):
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
        return salt_factories.SaltCpCLI(
            script_path, config=self.cache["masters"][master_id].config, **cli_kwargs
        )

    def get_salt_key(self, request, master_id, **cli_kwargs):
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
        return salt_factories.SaltKeyCLI(
            script_path, config=self.cache["masters"][master_id].config, **cli_kwargs
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
            max_attempts=3,
            **extra_daemon_class_kwargs
        )
        self.cache["daemons"][daemon_id] = proc
        if self.stats_processes:
            self.stats_processes[proc.get_display_name()] = psutil.Process(proc.pid)
        request.addfinalizer(proc.terminate)
        request.addfinalizer(lambda: self.cache["daemons"].pop(daemon_id))
        return proc

    def _start_daemon(
        self, request, script_name, daemon_config, daemon_class, cache_key, daemon_id
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
            max_attempts=3,
            event_listener=self.event_listener,
        )
        self.cache[cache_key][daemon_id] = proc
        if self.stats_processes:
            self.stats_processes[proc.get_display_name()] = psutil.Process(proc.pid)
        request.addfinalizer(proc.terminate)
        request.addfinalizer(lambda: self.cache[cache_key].pop(daemon_id))
        return proc

    def _get_root_dir_for_daemon(self, daemon_id):
        counter = 1
        root_dir = self.root_dir.join(daemon_id)
        while True:
            if not root_dir.check(dir=True):
                break
            root_dir = self.root_dir.join("{}_{}".format(daemon_id, counter))
            counter += 1
        root_dir.ensure(dir=True)
        return root_dir
