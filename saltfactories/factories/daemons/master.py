"""
..
    PYTEST_DONT_REWRITE


saltfactories.factories.daemons.master
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Salt Master Factory
"""
import pathlib

import attr
import salt.config
import salt.utils.dictupdate
import salt.utils.files

from saltfactories.factories.base import SaltDaemonFactory
from saltfactories.utils import ports


@attr.s(kw_only=True, slots=True)
class SaltMasterFactory(SaltDaemonFactory):
    @staticmethod
    def default_config(
        root_dir, master_id, config_defaults=None, config_overrides=None, order_masters=False,
    ):
        if config_defaults is None:
            config_defaults = {}

        conf_dir = root_dir / "conf"
        conf_dir.mkdir(parents=True, exist_ok=True)
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
            "api_pidfile": "run/api.pid",
            "pki_dir": "pki",
            "cachedir": "cache",
            "timeout": 3,
            "sock_dir": "run/master",
            "fileserver_list_cache_time": 0,
            "fileserver_backend": ["roots"],
            "pillar_opts": False,
            "peer": {".*": ["test.*"]},
            "log_file": "logs/master.log",
            "log_level_logfile": "debug",
            "api_logfile": "logs/api.log",
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
            "order_masters": order_masters,
            "max_open_files": 10240,
            "pytest-master": {"log": {"prefix": "{{cli_name}}({})".format(master_id)}},
        }
        # Merge in the initial default options with the internal _config_defaults
        salt.utils.dictupdate.update(config_defaults, _config_defaults, merge_lists=True)

        if config_overrides:
            # Merge in the default options with the master_config_overrides
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
        order_masters=False,
        master_of_masters_id=None,
    ):
        if config_overrides is None:
            _config_overrides = {}
        else:
            _config_overrides = config_overrides.copy()
        if master_of_masters_id is not None:
            master_of_masters = factories_manager.cache["masters"].get(master_of_masters_id)
            if master_of_masters is None:
                raise RuntimeError("No config found for {}".format(master_of_masters_id))
            master_of_masters_config = master_of_masters.config
            _config_overrides["syndic_master"] = master_of_masters_config["interface"]
            _config_overrides["syndic_master_port"] = master_of_masters_config["ret_port"]
        return cls.default_config(
            root_dir,
            daemon_id,
            config_defaults=config_defaults,
            config_overrides=_config_overrides,
            order_masters=order_masters,
        )

    @classmethod
    def _get_verify_config_entries(cls, config):
        # verify env to make sure all required directories are created and have the
        # right permissions
        pki_dir = pathlib.Path(config["pki_dir"])
        verify_env_entries = [
            str(pki_dir / "minions"),
            str(pki_dir / "minions_pre"),
            str(pki_dir / "minions_rejected"),
            str(pki_dir / "accepted"),
            str(pki_dir / "rejected"),
            str(pki_dir / "pending"),
            str(pathlib.Path(config["log_file"]).parent),
            str(pathlib.Path(config["cachedir"]) / "proc"),
            str(pathlib.Path(config["cachedir"]) / "jobs"),
            # config['extension_modules'],
            config["sock_dir"],
        ]
        verify_env_entries += config["file_roots"]["base"]
        verify_env_entries += config["file_roots"]["prod"]
        verify_env_entries += config["pillar_roots"]["base"]
        verify_env_entries += config["pillar_roots"]["prod"]
        return verify_env_entries

    @classmethod
    def load_config(cls, config_file, config):
        return salt.config.master_config(config_file)

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        yield self.config["id"], "salt/master/{id}/start".format(**self.config)

    # The following methods just route the calls to the right method in the factories manager
    # while making sure the CLI tools are referring to this daemon
    def get_salt_master_daemon(self, master_id, **kwargs):
        """
        This method will configure a master under a master-of-masters.

        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.get_salt_master_daemon`
        """
        return self.factories_manager.get_salt_master_daemon(
            master_id, master_of_masters_id=self.id, **kwargs
        )

    def get_salt_minion_daemon(self, minion_id, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.configure_salt_minion`
        """
        return self.factories_manager.get_salt_minion_daemon(minion_id, master_id=self.id, **kwargs)

    def get_salt_proxy_minion_daemon(self, minion_id, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.get_salt_proxy_minion_daemon`
        """
        return self.factories_manager.get_salt_proxy_minion_daemon(
            minion_id, master_id=self.id, **kwargs
        )

    def get_salt_api_daemon(self, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.get_salt_api_daemon`
        """
        return self.factories_manager.get_salt_api_daemon(self.id, **kwargs)

    def get_salt_syndic_daemon(self, syndic_id, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.get_salt_syndic_daemon`
        """
        return self.factories_manager.get_salt_syndic_daemon(
            syndic_id, master_of_masters_id=self.id, **kwargs
        )

    def get_salt_cloud_cli(self, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.get_salt_cloud_cli`
        """
        return self.factories_manager.get_salt_cloud_cli(self.id, **kwargs)

    def get_salt_cli(self, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.get_salt_cli`
        """
        return self.factories_manager.get_salt_cli(self.id, **kwargs)

    def get_salt_cp_cli(self, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.get_salt_cp_cli`
        """
        return self.factories_manager.get_salt_cp_cli(self.id, **kwargs)

    def get_salt_key_cli(self, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.get_salt_key_cli`
        """
        return self.factories_manager.get_salt_key_cli(self.id, **kwargs)

    def get_salt_run_cli(self, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.get_salt_run_cli`
        """
        return self.factories_manager.get_salt_run_cli(self.id, **kwargs)

    def get_salt_spm_cli(self, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.get_salt_spm_cli`
        """
        return self.factories_manager.get_salt_spm_cli(self.id, **kwargs)

    def get_salt_ssh_cli(self, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.get_salt_ssh_cli`
        """
        return self.factories_manager.get_salt_ssh_cli(self.id, **kwargs)
