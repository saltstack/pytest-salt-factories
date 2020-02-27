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

import saltfactories
from saltfactories.factories import master
from saltfactories.factories import minion
from saltfactories.factories import proxy
from saltfactories.factories import syndic
from saltfactories.utils import cli_scripts
from saltfactories.utils import event_listener
from saltfactories.utils import processes


class SaltFactoriesManager(object):
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
        start_timeout=10,
    ):
        self.pytestconfig = pytestconfig
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
        }
        self.event_listener = event_listener.EventListener()
        self.event_listener.start()

    @staticmethod
    def get_running_username():
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
        return os.path.join(saltfactories.CODE_ROOT_DIR, "utils", "salt", "log_handlers")

    @staticmethod
    def get_salt_engines_path():
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
        if minion_id in self.cache["configs"]["minions"]:
            return self.cache["configs"]["minions"][minion_id]

        master_port = None
        if master_id is not None:
            master_config = self.cache["configs"]["masters"][master_id]
            master_port = master_config.get("ret_port")
        default_options = self.pytestconfig.hook.pytest_saltfactories_generate_default_minion_configuration(
            request=request, factories_manager=self, minion_id=minion_id, master_port=master_port
        )
        config_overrides = self.pytestconfig.hook.pytest_saltfactories_minion_configuration_overrides(
            request=request,
            factories_manager=self,
            minion_id=minion_id,
            default_options=default_options,
        )
        minion_config = minion.MinionFactory.default_config(
            self.root_dir,
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
        if minion_id in self.cache["minions"]:
            raise RuntimeError("A minion by the ID of '{}' was already spawned".format(minion_id))

        minion_config = self.cache["configs"]["minions"].get(minion_id)
        if minion_config is None:
            minion_config = self.configure_minion(request, minion_id, master_id=master_id)

        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            "salt-minion",
            executable=self.executable,
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        proc = processes.start_daemon(
            minion_config,
            script_path,
            processes.SaltMinion,
            # start_timeout=self.start_timeout,
            start_timeout=20,
            slow_stop=self.slow_stop,
            environ=self.environ,
            cwd=self.cwd,
            max_attempts=3,
            event_listener=self.event_listener,
        )
        self.cache["minions"][minion_id] = proc
        request.addfinalizer(proc.terminate)
        request.addfinalizer(lambda: self.cache["minions"].pop(minion_id))
        return proc

    def configure_master(self, request, master_id, order_masters=False, master_of_masters_id=None):
        if master_id in self.cache["configs"]["masters"]:
            return self.cache["configs"]["masters"][master_id]

        default_options = self.pytestconfig.hook.pytest_saltfactories_generate_default_master_configuration(
            request=request,
            factories_manager=self,
            master_id=master_id,
            order_masters=order_masters,
        )
        config_overrides = self.pytestconfig.hook.pytest_saltfactories_master_configuration_overrides(
            request=request,
            factories_manager=self,
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
            self.root_dir,
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

        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            "salt-master",
            executable=self.executable,
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        proc = processes.start_daemon(
            master_config,
            script_path,
            processes.SaltMaster,
            start_timeout=self.start_timeout,
            slow_stop=self.slow_stop,
            environ=self.environ,
            cwd=self.cwd,
            max_attempts=3,
            event_listener=self.event_listener,
        )
        self.cache["masters"][master_id] = proc
        request.addfinalizer(proc.terminate)
        request.addfinalizer(lambda: self.cache["masters"].pop(master_id))
        return proc

    def configure_syndic(self, request, syndic_id, master_of_masters_id=None):
        """
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

        default_options = self.pytestconfig.hook.pytest_saltfactories_generate_default_syndic_configuration(
            request=request,
            factories_manager=self,
            syndic_id=syndic_id,
            syndic_master_port=syndic_master_port,
        )

        config_overrides = self.pytestconfig.hook.pytest_saltfactories_syndic_configuration_overrides(
            request=request,
            factories_manager=self,
            syndic_id=syndic_id,
            default_options=default_options,
        )

        syndic_setup_config = syndic.SyndicFactory.default_config(
            self.root_dir,
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

        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            "salt-syndic",
            executable=self.executable,
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        proc = processes.start_daemon(
            syndic_config,
            script_path,
            processes.SaltSyndic,
            start_timeout=self.start_timeout,
            slow_stop=self.slow_stop,
            environ=self.environ,
            cwd=self.cwd,
            max_attempts=3,
            event_listener=self.event_listener,
        )
        self.cache["syndics"][syndic_id] = proc
        request.addfinalizer(proc.terminate)
        request.addfinalizer(lambda: self.cache["syndics"].pop(syndic_id))
        return proc

    def configure_proxy_minion(self, request, proxy_minion_id, master_id=None):
        if proxy_minion_id in self.cache["configs"]["proxy_minions"]:
            return self.cache["configs"]["proxy_minions"][proxy_minion_id]

        master_port = None
        if master_id is not None:
            master_config = self.cache["configs"]["masters"][master_id]
            master_port = master_config.get("ret_port")
        default_options = self.pytestconfig.hook.pytest_saltfactories_generate_default_proxy_minion_configuration(
            request=request,
            factories_manager=self,
            proxy_minion_id=proxy_minion_id,
            master_port=master_port,
        )
        config_overrides = self.pytestconfig.hook.pytest_saltfactories_proxy_minion_configuration_overrides(
            request=request,
            factories_manager=self,
            proxy_minion_id=proxy_minion_id,
            default_options=default_options,
        )
        proxy_minion_config = proxy.ProxyMinionFactory.default_config(
            self.root_dir,
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
        if proxy_minion_id in self.cache["proxy_minions"]:
            raise RuntimeError(
                "A proxy_minion by the ID of '{}' was already spawned".format(proxy_minion_id)
            )

        proxy_minion_config = self.cache["configs"]["proxy_minions"].get(proxy_minion_id)
        if proxy_minion_config is None:
            proxy_minion_config = self.configure_proxy_minion(
                request, proxy_minion_id, master_id=master_id
            )

        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            "salt-proxy",
            executable=self.executable,
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        proc = processes.start_daemon(
            proxy_minion_config,
            script_path,
            processes.SaltProxyMinion,
            # start_timeout=self.start_timeout,
            start_timeout=20,
            slow_stop=self.slow_stop,
            environ=self.environ,
            cwd=self.cwd,
            max_attempts=3,
            event_listener=self.event_listener,
        )
        self.cache["proxy_minions"][proxy_minion_id] = proc
        request.addfinalizer(proc.terminate)
        request.addfinalizer(lambda: self.cache["proxy_minions"].pop(proxy_minion_id))
        return proc

    def get_salt_cli(self, request, master_id):
        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            "salt",
            executable=self.executable,
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        return processes.SaltCLI(script_path, config=self.cache["masters"][master_id].config)

    def get_salt_call_cli(self, request, minion_id):
        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            "salt-call",
            executable=self.executable,
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        try:
            return processes.SaltCallCLI(
                script_path, config=self.cache["minions"][minion_id].config
            )
        except KeyError:
            try:
                return processes.SaltCallCLI(
                    script_path,
                    base_script_args=["--proxyid={}".format(minion_id)],
                    config=self.cache["proxy_minions"][minion_id].config,
                )
            except KeyError:
                raise KeyError(
                    "Could not find {} in the minions or proxy minions caches".format(minion_id)
                )

    def get_salt_run(self, request, master_id):
        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            "salt-run",
            executable=self.executable,
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        return processes.SaltRunCLI(script_path, config=self.cache["masters"][master_id].config)

    def get_salt_cp(self, request, master_id):
        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            "salt-cp",
            executable=self.executable,
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        return processes.SaltCpCLI(script_path, config=self.cache["masters"][master_id].config)

    def get_salt_key(self, request, master_id):
        script_path = cli_scripts.generate_script(
            self.scripts_dir,
            "salt-key",
            executable=self.executable,
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )
        return processes.SaltKeyCLI(script_path, config=self.cache["masters"][master_id].config)
