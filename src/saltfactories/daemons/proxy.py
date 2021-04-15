"""
..
    PYTEST_DONT_REWRITE


Salt Proxy Minion Factory
"""
import copy
import logging
import pathlib
import shutil
import sys

import attr
import salt.config
import salt.utils.dictupdate

from saltfactories import cli
from saltfactories.bases import SaltDaemon
from saltfactories.bases import SystemdSaltDaemonImpl
from saltfactories.utils import cli_scripts
from saltfactories.utils import ports
from saltfactories.utils.tempfiles import SaltPillarTree
from saltfactories.utils.tempfiles import SaltStateTree

log = logging.getLogger(__name__)


class SystemdSaltProxyImpl(SystemdSaltDaemonImpl):
    def get_service_name(self):
        if self._service_name is None:
            self._service_name = "{}@{}".format(super().get_service_name(), self.factory.id)
        return self._service_name


@attr.s(kw_only=True, slots=True)
class SaltProxyMinion(SaltDaemon):

    include_proxyid_cli_flag = attr.ib(default=True, repr=False)

    state_tree = attr.ib(init=False, hash=False, repr=False)
    pillar_tree = attr.ib(init=False, hash=False, repr=False)

    def _get_impl_class(self):
        if self.system_install:
            return SystemdSaltProxyImpl
        return super()._get_impl_class()

    @state_tree.default
    def __setup_state_tree(self):
        if "file_roots" in self.config:
            return SaltStateTree(envs=copy.deepcopy(self.config.get("file_roots") or {}))

    @pillar_tree.default
    def __setup_pillar_tree(self):
        if "pillar_roots" in self.config:
            return SaltPillarTree(envs=copy.deepcopy(self.config.get("pillar_roots") or {}))

    @classmethod
    def default_config(
        cls,
        root_dir,
        proxy_minion_id,
        defaults=None,
        overrides=None,
        master=None,
        system_install=False,
    ):
        if defaults is None:
            defaults = {}

        master_id = master_port = None
        if master is not None:
            master_id = master.id
            master_port = master.config["ret_port"]
            # Match transport if not set
            defaults.setdefault("transport", master.config["transport"])

        if system_install is True:
            conf_dir = root_dir / "etc" / "salt"
            conf_dir.mkdir(parents=True, exist_ok=True)
            conf_file = str(conf_dir / "proxy")
            pki_dir = conf_dir / "pki" / "minion"

            logs_dir = root_dir / "var" / "log" / "salt"
            logs_dir.mkdir(parents=True, exist_ok=True)

            state_tree_root = root_dir / "srv" / "salt"
            state_tree_root.mkdir(parents=True, exist_ok=True)
            pillar_tree_root = root_dir / "srv" / "pillar"
            pillar_tree_root.mkdir(parents=True, exist_ok=True)

            _defaults = {
                "id": proxy_minion_id,
                "conf_file": conf_file,
                "root_dir": str(root_dir),
                "interface": "127.0.0.1",
                "master": "127.0.0.1",
                "master_port": master_port or salt.config.DEFAULT_MINION_OPTS["master_port"],
                "tcp_pub_port": salt.config.DEFAULT_MINION_OPTS["tcp_pub_port"],
                "tcp_pull_port": salt.config.DEFAULT_MINION_OPTS["tcp_pull_port"],
                "pki_dir": str(pki_dir),
                "log_file": str(logs_dir / "proxy.log"),
                "log_level_logfile": "debug",
                "loop_interval": 0.05,
                "log_fmt_console": "%(asctime)s,%(msecs)03.0f [%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
                "log_fmt_logfile": "[%(asctime)s,%(msecs)03.0f][%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
                "file_roots": {
                    "base": [str(state_tree_root)],
                },
                "pillar_roots": {
                    "base": [str(pillar_tree_root)],
                },
                "proxy": {"proxytype": "dummy"},
                "pytest-minion": {
                    "master-id": master_id,
                    "log": {"prefix": "{}(id={!r})".format(cls.__name__, proxy_minion_id)},
                },
            }
        else:
            conf_dir = root_dir / "conf"
            conf_dir.mkdir(parents=True, exist_ok=True)
            conf_file = str(conf_dir / "proxy")

            state_tree_root = root_dir / "state-tree"
            state_tree_root.mkdir(exist_ok=True)
            state_tree_root_base = state_tree_root / "base"
            state_tree_root_base.mkdir(exist_ok=True)
            state_tree_root_prod = state_tree_root / "prod"
            state_tree_root_prod.mkdir(exist_ok=True)
            pillar_tree_root = root_dir / "pillar-tree"
            pillar_tree_root.mkdir(exist_ok=True)
            pillar_tree_root_base = pillar_tree_root / "base"
            pillar_tree_root_base.mkdir(exist_ok=True)
            pillar_tree_root_prod = pillar_tree_root / "prod"
            pillar_tree_root_prod.mkdir(exist_ok=True)

            _defaults = {
                "id": proxy_minion_id,
                "conf_file": conf_file,
                "root_dir": str(root_dir),
                "interface": "127.0.0.1",
                "master": "127.0.0.1",
                "master_port": master_port or ports.get_unused_localhost_port(),
                "tcp_pub_port": ports.get_unused_localhost_port(),
                "tcp_pull_port": ports.get_unused_localhost_port(),
                "pidfile": "run/proxy.pid",
                "pki_dir": "pki",
                "cachedir": "cache",
                "sock_dir": "run/proxy",
                "log_file": "logs/proxy.log",
                "log_level_logfile": "debug",
                "loop_interval": 0.05,
                "log_fmt_console": "%(asctime)s,%(msecs)03.0f [%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
                "log_fmt_logfile": "[%(asctime)s,%(msecs)03.0f][%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
                "file_roots": {
                    "base": [str(state_tree_root_base)],
                    "prod": [str(state_tree_root_prod)],
                },
                "pillar_roots": {
                    "base": [str(pillar_tree_root_base)],
                    "prod": [str(pillar_tree_root_prod)],
                },
                "proxy": {"proxytype": "dummy"},
                "enable_legacy_startup_events": False,
                "acceptance_wait_time": 0.5,
                "acceptance_wait_time_max": 5,
                "pytest-minion": {
                    "master-id": master_id,
                    "log": {"prefix": "{}(id={!r})".format(cls.__name__, proxy_minion_id)},
                },
            }
        # Merge in the initial default options with the internal _defaults
        salt.utils.dictupdate.update(defaults, _defaults, merge_lists=True)

        if overrides:
            # Merge in the default options with the proxy_overrides
            salt.utils.dictupdate.update(defaults, overrides, merge_lists=True)

        return defaults

    @classmethod
    def _configure(  # pylint: disable=arguments-differ
        cls,
        factories_manager,
        daemon_id,
        root_dir=None,
        defaults=None,
        overrides=None,
        master=None,
    ):
        return cls.default_config(
            root_dir,
            daemon_id,
            defaults=defaults,
            overrides=overrides,
            master=master,
            system_install=factories_manager.system_install,
        )

    @classmethod
    def _get_verify_config_entries(cls, config):
        # verify env to make sure all required directories are created and have the
        # right permissions
        verify_env_entries = [
            str(pathlib.Path(config["log_file"]).parent),
            # config['extension_modules'],
            config["sock_dir"],
        ]
        verify_env_entries.extend(config["file_roots"]["base"])
        if "prod" in config["file_roots"]:
            verify_env_entries.extend(config["file_roots"]["prod"])
        verify_env_entries.extend(config["pillar_roots"]["base"])
        if "prod" in config["pillar_roots"]:
            verify_env_entries.extend(config["pillar_roots"]["prod"])
        return verify_env_entries

    @classmethod
    def load_config(cls, config_file, config):
        return salt.config.proxy_config(config_file, minion_id=config["id"], cache_minion_id=True)

    def get_base_script_args(self):
        script_args = super().get_base_script_args()
        if sys.platform.startswith("win") is False:
            script_args.append("--disable-keepalive")
        return script_args

    def cmdline(self, *args):
        if self.include_proxyid_cli_flag is False:
            return super().cmdline(*args)
        _args = []
        for arg in args:
            if arg.startswith("--proxyid"):
                break
        else:
            _args.append("--proxyid={}".format(self.id))
        return super().cmdline(*(_args + list(args)))

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        pytest_config = self.config["pytest-{}".format(self.config["__role"])]
        if not pytest_config.get("master-id"):
            log.warning(
                "Will not be able to check for start events for %s since it's missing the 'master-id' key "
                "in the 'pytest-%s' dictionary, or it's value is None.",
                self,
                self.config["__role"],
            )
        else:
            yield pytest_config["master-id"], "salt/{role}/{id}/start".format(
                role=self.config["__role"], id=self.id
            )

    def salt_call_cli(self, factory_class=cli.call.SaltCall, **factory_class_kwargs):
        """
        Return a `salt-call` CLI process for this minion instance
        """
        if self.system_install is False:
            script_path = cli_scripts.generate_script(
                self.factories_manager.scripts_dir,
                "salt-call",
                code_dir=self.factories_manager.code_dir,
                inject_coverage=self.factories_manager.inject_coverage,
                inject_sitecustomize=self.factories_manager.inject_sitecustomize,
            )
        else:
            script_path = shutil.which("salt-call")
        return factory_class(
            script_name=script_path,
            config=self.config.copy(),
            base_script_args=["--proxyid={}".format(self.id)],
            system_install=self.factories_manager.system_install,
            **factory_class_kwargs
        )
