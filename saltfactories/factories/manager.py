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

from saltfactories.factories import master
from saltfactories.factories import minion
from saltfactories.factories import syndic
from saltfactories.utils import cli_scripts
from saltfactories.utils import processes


CODE_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IS_WINDOWS = sys.platform.startswith("win")


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
        fail_callable=None,
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
        self.fail_callable = fail_callable
        self.slow_stop = slow_stop
        self.start_timeout = start_timeout
        self.scripts_dir = root_dir.join("scripts").ensure(dir=True).strpath
        self.configs = {"minions": {}, "masters": {}}
        self.masters = {}
        self.minions = {}
        self.cache = {
            "configs": {"masters": {}, "minions": {}, "syndics": {}},
            "masters": {},
            "minions": {},
            "syndics": {},
        }

    @staticmethod
    def get_running_username():
        try:
            return SaltFactoriesManager.get_running_username.__username__
        except AttributeError:
            if IS_WINDOWS:
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
        return os.path.join(CODE_ROOT_DIR, "utils", "salt", "log_handlers")

    @staticmethod
    def get_salt_engines_path():
        return os.path.join(CODE_ROOT_DIR, "utils", "salt", "engines")

    def final_minion_config_tweaks(self, config):
        self.final_common_config_tweaks(config)

    def final_master_config_tweaks(self, config):
        self.final_common_config_tweaks(config)

    def final_syndic_config_tweaks(self, config):
        self.final_common_config_tweaks(config)

    def final_common_config_tweaks(self, config):
        config.setdefault("engines", [])
        if "pytest" not in config["engines"]:
            config["engines"].append("pytest")

        if "engines_dirs" not in config:
            config["engines_dirs"] = []
        config["engines_dirs"].insert(0, SaltFactoriesManager.get_salt_engines_path())
        config["user"] = SaltFactoriesManager.get_running_username()
        if "log_handlers_dirs" not in config:
            config["log_handlers_dirs"] = []
        config["log_handlers_dirs"].insert(0, SaltFactoriesManager.get_salt_log_handlers_path())

        config.setdefault("pytest", {}).setdefault("log", {})
        config["pytest"]["log"]["host"] = "localhost"
        config["pytest"]["log"]["port"] = self.log_server_port
        config["pytest"]["log"]["level"] = self.log_server_level

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
            fail_callable=self.fail_callable,
            # start_timeout=self.start_timeout,
            start_timeout=20,
            slow_stop=self.slow_stop,
            environ=self.environ,
            cwd=self.cwd,
            max_attempts=3,
        )
        self.cache["minions"][minion_id] = proc
        request.addfinalizer(proc.terminate)
        request.addfinalizer(lambda: self.cache["minions"].pop(minion_id))
        return proc

    def configure_master(self, request, master_id):
        if master_id in self.cache["configs"]["masters"]:
            return self.cache["configs"]["masters"][master_id]
        default_options = self.pytestconfig.hook.pytest_saltfactories_generate_default_master_configuration(
            request=request, factories_manager=self, master_id=master_id
        )
        config_overrides = self.pytestconfig.hook.pytest_saltfactories_master_configuration_overrides(
            request=request,
            factories_manager=self,
            master_id=master_id,
            default_options=default_options,
        )
        master_config = master.MasterFactory.default_config(
            self.root_dir,
            master_id=master_id,
            default_options=default_options,
            config_overrides=config_overrides,
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

    def spawn_master(self, request, master_id):
        if master_id in self.cache["masters"]:
            raise RuntimeError("A master by the ID of '{}' was already spawned".format(master_id))

        master_config = self.cache["configs"]["masters"].get(master_id)
        if master_config is None:
            master_config = self.configure_master(request, master_id)

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
            fail_callable=self.fail_callable,
            start_timeout=self.start_timeout,
            slow_stop=self.slow_stop,
            environ=self.environ,
            cwd=self.cwd,
            max_attempts=3,
        )
        self.cache["masters"][master_id] = proc
        request.addfinalizer(proc.terminate)
        request.addfinalizer(lambda: self.cache["masters"].pop(master_id))
        return proc

    def configure_syndic(self, request, syndic_id, master_id=None):
        if syndic_id in self.cache["configs"]["syndics"]:
            return self.cache["configs"]["syndics"][syndic_id]

        master_config = self.cache["configs"]["masters"].get(master_id)
        if master_config is None and master_id:
            master_config = self.configure_master(request, master_id)

        master_port = None
        if master_config:
            master_port = master_config.get("ret_port")

        default_options = self.pytestconfig.hook.pytest_saltfactories_generate_default_syndic_configuration(
            request=request, factories_manager=self, syndic_id=syndic_id, master_port=master_port
        )
        config_overrides = self.pytestconfig.hook.pytest_saltfactories_syndic_configuration_overrides(
            request=request,
            factories_manager=self,
            syndic_id=syndic_id,
            default_options=default_options,
        )
        syndic_config = syndic.SyndicFactory.default_config(
            self.root_dir,
            syndic_id=syndic_id,
            default_options=default_options,
            config_overrides=config_overrides,
            master_port=master_port,
        )
        self.final_syndic_config_tweaks(syndic_config)
        syndic_config = self.pytestconfig.hook.pytest_saltfactories_write_syndic_configuration(
            request=request, syndic_config=syndic_config
        )
        self.pytestconfig.hook.pytest_saltfactories_verify_syndic_configuration(
            request=request,
            syndic_config=syndic_config,
            username=SaltFactoriesManager.get_running_username(),
        )
        self.cache["configs"]["syndics"][syndic_id] = syndic_config
        request.addfinalizer(lambda: self.cache["configs"]["syndics"].pop(syndic_id))
        return syndic_config

    def spawn_syndic(self, request, syndic_id, master_id=None):
        if syndic_id in self.cache["syndics"]:
            raise RuntimeError("A syndic by the ID of '{}' was already spawned".format(syndic_id))

        syndic_config = self.cache["configs"]["syndics"].get(syndic_id)
        if syndic_config is None:
            syndic_config = self.configure_syndic(request, syndic_id, master_id=master_id)

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
            fail_callable=self.fail_callable,
            start_timeout=self.start_timeout,
            slow_stop=self.slow_stop,
            environ=self.environ,
            cwd=self.cwd,
            max_attempts=3,
        )
        self.cache["syndics"][syndic_id] = proc
        request.addfinalizer(proc.terminate)
        request.addfinalizer(lambda: self.cache["syndics"].pop(syndic_id))
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
