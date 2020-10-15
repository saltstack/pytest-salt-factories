"""
..
    PYTEST_DONT_REWRITE


saltfactories.factories.daemons.minion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Salt Minion Factory
"""
import logging
import pathlib
import shutil
import sys

import attr
import salt.config
import salt.utils.dictupdate

from saltfactories.factories import cli
from saltfactories.factories.base import SaltDaemonFactory
from saltfactories.utils import cli_scripts
from saltfactories.utils import ports

log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True)
class SaltMinionFactory(SaltDaemonFactory):
    @classmethod
    def default_config(
        cls,
        root_dir,
        minion_id,
        config_defaults=None,
        config_overrides=None,
        master=None,
        system_install=False,
    ):
        if config_defaults is None:
            config_defaults = {}

        master_id = master_port = None
        if master is not None:
            master_id = master.id
            master_port = master.config["ret_port"]
            # Match transport if not set
            config_defaults.setdefault("transport", master.config["transport"])

        if system_install is True:

            conf_dir = root_dir / "etc" / "salt"
            conf_dir.mkdir(parents=True, exist_ok=True)
            conf_file = str(conf_dir / "minion")
            pki_dir = conf_dir / "pki" / "minion"

            logs_dir = root_dir / "var" / "log" / "salt"
            logs_dir.mkdir(parents=True, exist_ok=True)

            _config_defaults = {
                "id": master_id,
                "conf_file": conf_file,
                "root_dir": str(root_dir),
                "interface": "127.0.0.1",
                "master": "127.0.0.1",
                "master_port": master_port or salt.config.DEFAULT_MINION_OPTS["master_port"],
                "tcp_pub_port": salt.config.DEFAULT_MINION_OPTS["tcp_pub_port"],
                "tcp_pull_port": salt.config.DEFAULT_MINION_OPTS["tcp_pull_port"],
                "pki_dir": str(pki_dir),
                "log_file": str(logs_dir / "minion.log"),
                "log_level_logfile": "debug",
                "log_fmt_console": "%(asctime)s,%(msecs)03.0f [%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
                "log_fmt_logfile": "[%(asctime)s,%(msecs)03.0f][%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
                "pytest-minion": {
                    "master-id": master_id,
                    "log": {"prefix": "{}(id={!r})".format(cls.__name__, minion_id)},
                },
            }
        else:
            conf_dir = root_dir / "conf"
            conf_dir.mkdir(parents=True, exist_ok=True)
            conf_file = str(conf_dir / "minion")

            _config_defaults = {
                "id": minion_id,
                "conf_file": conf_file,
                "root_dir": str(root_dir),
                "interface": "127.0.0.1",
                "master": "127.0.0.1",
                "master_port": master_port or ports.get_unused_localhost_port(),
                "tcp_pub_port": ports.get_unused_localhost_port(),
                "tcp_pull_port": ports.get_unused_localhost_port(),
                "pidfile": "run/minion.pid",
                "pki_dir": "pki",
                "cachedir": "cache",
                "sock_dir": "run/minion",
                "log_file": "logs/minion.log",
                "log_level_logfile": "debug",
                "loop_interval": 0.05,
                "log_fmt_console": "%(asctime)s,%(msecs)03.0f [%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
                "log_fmt_logfile": "[%(asctime)s,%(msecs)03.0f][%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
                "enable_legacy_startup_events": False,
                "acceptance_wait_time": 0.5,
                "acceptance_wait_time_max": 5,
                "pytest-minion": {
                    "master-id": master_id,
                    "log": {"prefix": "{}(id={!r})".format(cls.__name__, minion_id)},
                },
            }
        # Merge in the initial default options with the internal _config_defaults
        salt.utils.dictupdate.update(config_defaults, _config_defaults, merge_lists=True)

        if config_overrides:
            # Merge in the default options with the minion_config_overrides
            salt.utils.dictupdate.update(config_defaults, config_overrides, merge_lists=True)

        return config_defaults

    @classmethod
    def _configure(  # pylint: disable=arguments-differ
        cls,
        factories_manager,
        daemon_id,
        root_dir=None,
        config_defaults=None,
        config_overrides=None,
        master=None,
    ):
        return cls.default_config(
            root_dir,
            daemon_id,
            config_defaults=config_defaults,
            config_overrides=config_overrides,
            master=master,
            system_install=factories_manager.system_install,
        )

    @classmethod
    def _get_verify_config_entries(cls, config):
        # verify env to make sure all required directories are created and have the
        # right permissions
        pki_dir = pathlib.Path(config["pki_dir"])
        return [
            str(pki_dir / "minions"),
            str(pki_dir / "minions_pre"),
            str(pki_dir / "minions_rejected"),
            str(pki_dir / "accepted"),
            str(pki_dir / "rejected"),
            str(pki_dir / "pending"),
            str(pathlib.Path(config["log_file"]).parent),
            str(pathlib.Path(config["cachedir"]) / "proc"),
            # config['extension_modules'],
            config["sock_dir"],
        ]

    @classmethod
    def load_config(cls, config_file, config):
        return salt.config.minion_config(config_file, minion_id=config["id"], cache_minion_id=True)

    def get_script_args(self):
        args = super().get_script_args()
        if sys.platform.startswith("win") is False:
            args.append("--disable-keepalive")
        return args

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

    def get_salt_call_cli(self, factory_class=cli.call.SaltCallCliFactory, **factory_class_kwargs):
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
            cli_script_name=script_path,
            config=self.config.copy(),
            system_install=self.factories_manager.system_install,
            **factory_class_kwargs
        )
