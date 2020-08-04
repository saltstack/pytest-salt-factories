"""
..
    PYTEST_DONT_REWRITE


saltfactories.factories.daemons.syndic
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Salt Syndic Factory
"""
import logging
import pathlib

import attr
import salt.config
import salt.utils.dictupdate
import salt.utils.files

from saltfactories.factories.base import SaltDaemonFactory
from saltfactories.utils import ports

log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True)
class SaltSyndicFactory(SaltDaemonFactory):
    @staticmethod
    def default_config(
        root_dir, syndic_id, config_defaults=None, config_overrides=None, syndic_master_port=None,
    ):
        if config_defaults is None:
            config_defaults = {"syndic": {}}
        elif "syndic" in config_defaults and config_defaults["syndic"] is None:
            config_defaults["syndic"] = {}
        elif "syndic" not in config_defaults:
            config_defaults["syndic"] = {}

        if config_overrides is None:
            config_overrides = {}

        conf_dir = root_dir / "conf"
        conf_dir.mkdir(parents=True, exist_ok=True)
        conf_d_dir = conf_dir / "master.d"
        conf_d_dir.mkdir(exist_ok=True)
        conf_file = str(conf_d_dir / "syndic.conf")

        master_config = SaltSyndicFactory.default_master_config(
            root_dir,
            conf_dir,
            syndic_id,
            config_defaults=config_defaults.get("master"),
            config_overrides=config_overrides.get("master"),
        )
        minion_config = SaltSyndicFactory.default_minion_config(
            root_dir,
            conf_dir,
            syndic_id,
            config_defaults=config_defaults.get("minion"),
            config_overrides=config_overrides.get("minion"),
            master_port=master_config["ret_port"],
        )

        _config_defaults = {
            "id": syndic_id,
            "master_id": syndic_id,
            "conf_file": conf_file,
            "root_dir": str(root_dir),
            "syndic_master": "127.0.0.1",
            "syndic_master_port": syndic_master_port or ports.get_unused_localhost_port(),
            "syndic_pidfile": "run/syndic.pid",
            "syndic_log_file": "logs/syndic.log",
            "syndic_log_level_logfile": "debug",
            "syndic_dir": "cache/syndics",
            "pytest-syndic": {"log": {"prefix": "{{cli_name}}({})".format(syndic_id)},},
        }
        # Merge in the initial default options with the internal _config_defaults
        salt.utils.dictupdate.update(
            config_defaults.get("syndic"), _config_defaults, merge_lists=True
        )

        if config_overrides.get("syndic"):
            # Merge in the default options with the syndic_config_overrides
            salt.utils.dictupdate.update(
                config_defaults.get("syndic"), config_overrides.get("syndic"), merge_lists=True
            )

        return {
            "master": master_config,
            "minion": minion_config,
            "syndic": config_defaults["syndic"],
        }

    @staticmethod
    def default_minion_config(
        root_dir, conf_dir, minion_id, config_defaults=None, config_overrides=None, master_port=None
    ):
        if config_defaults is None:
            config_defaults = {}

        conf_file = str(conf_dir / "minion")

        _config_defaults = {
            "id": minion_id,
            "master_id": minion_id,
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
            #'multiprocessing': False,
            "log_fmt_console": "%(asctime)s,%(msecs)03.0f [%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
            "log_fmt_logfile": "[%(asctime)s,%(msecs)03.0f][%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
            "hash_type": "sha256",
            "transport": "zeromq",
            "pytest-minion": {"log": {"prefix": "{{cli_name}}({})".format(minion_id)},},
        }
        # Merge in the initial default options with the internal _config_defaults
        salt.utils.dictupdate.update(config_defaults, _config_defaults, merge_lists=True)

        if config_overrides:
            # Merge in the default options with the minion_config_overrides
            salt.utils.dictupdate.update(config_defaults, config_overrides, merge_lists=True)

        return config_defaults

    @staticmethod
    def default_master_config(
        root_dir, conf_dir, master_id, config_defaults=None, config_overrides=None,
    ):
        if config_defaults is None:
            config_defaults = {}

        conf_file = str(conf_dir / "master")
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

        _config_defaults = {
            "id": master_id,
            "master_id": master_id,
            "conf_file": conf_file,
            "root_dir": str(root_dir),
            "interface": "127.0.0.1",
            "publish_port": ports.get_unused_localhost_port(),
            "ret_port": ports.get_unused_localhost_port(),
            "tcp_master_pub_port": ports.get_unused_localhost_port(),
            "tcp_master_pull_port": ports.get_unused_localhost_port(),
            "tcp_master_publish_pull": ports.get_unused_localhost_port(),
            "tcp_master_workers": ports.get_unused_localhost_port(),
            "worker_threads": 3,
            "pidfile": "run/master.pid",
            "pki_dir": "pki",
            "cachedir": "cache",
            "timeout": 3,
            "sock_dir": "run/master",
            "open_mode": True,
            "fileserver_list_cache_time": 0,
            "fileserver_backend": ["roots"],
            "pillar_opts": False,
            "peer": {".*": ["test.*"]},
            "log_file": "logs/master.log",
            "log_level_logfile": "debug",
            "key_logfile": "logs/key.log",
            "token_dir": "tokens",
            "token_file": str(root_dir / "ksfjhdgiuebfgnkefvsikhfjdgvkjahcsidk"),
            "file_buffer_size": 8192,
            "log_fmt_console": "%(asctime)s,%(msecs)03.0f [%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
            "log_fmt_logfile": "[%(asctime)s,%(msecs)03.0f][%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
            "file_roots": {"base": str(state_tree_root_base), "prod": str(state_tree_root_prod)},
            "pillar_roots": {
                "base": str(pillar_tree_root_base),
                "prod": str(pillar_tree_root_prod),
            },
            "hash_type": "sha256",
            "transport": "zeromq",
            "order_masters": False,
            "max_open_files": 10240,
            "pytest-master": {"log": {"prefix": "{{cli_name}}({})".format(master_id)},},
        }
        # Merge in the initial default options with the internal _config_defaults
        salt.utils.dictupdate.update(config_defaults, _config_defaults, merge_lists=True)

        if config_overrides:
            # Merge in the default options with the master_config_overrides
            salt.utils.dictupdate.update(config_defaults, config_overrides, merge_lists=True)

        # Remove syndic related options
        for key in list(config_defaults):
            if key.startswith("syndic_"):
                config_defaults.pop(key)

        return config_defaults

    @classmethod
    def _configure(  # pylint: disable=arguments-differ
        cls,
        factories_manager,
        daemon_id,
        root_dir=None,
        config_defaults=None,
        config_overrides=None,
        order_masters=False,
        master_of_masters_id=None,
    ):
        syndic_master_port = None
        if master_of_masters_id is not None:
            master_of_masters = factories_manager.cache["masters"].get(master_of_masters_id)
            if master_of_masters is None:
                raise RuntimeError("No config found for {}".format(master_of_masters_id))
            syndic_master_port = master_of_masters.config["ret_port"]

        return cls.default_config(
            root_dir,
            daemon_id,
            config_defaults=config_defaults,
            config_overrides=config_overrides,
            syndic_master_port=syndic_master_port,
        )

    @classmethod
    def _get_verify_config_entries(cls, config):
        # verify env to make sure all required directories are created and have the
        # right permissions
        verify_env_entries = [
            str(pathlib.Path(config["syndic_log_file"]).parent),
        ]
        return verify_env_entries

    @classmethod
    def load_config(cls, config_file, config):
        conf_dir = pathlib.Path(config_file).parent.parent
        master_config_file = str(conf_dir / "master")
        minion_config_file = str(conf_dir / "minion")
        return salt.config.syndic_config(master_config_file, minion_config_file)

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        pytest_config = self.config["pytest-{}".format(self.config["__role"])]
        if "master_config" not in pytest_config:
            log.warning(
                "Will not be able to check for start events for %s since it's missing 'master_config' key "
                "in the 'pytest-%s' dictionary",
                self,
                self.config["__role"],
            )
        else:
            yield pytest_config["master_config"]["id"], "salt/{__role}/{id}/start".format(
                **self.config
            )
