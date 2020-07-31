"""
..
    PYTEST_DONT_REWRITE


saltfactories.factories.daemons.master
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Salt Master Factory
"""
import attr
import salt.config
import salt.utils.dictupdate
import salt.utils.files

from saltfactories.factories.base import SaltDaemonFactory
from saltfactories.utils import ports


@attr.s(kw_only=True, slots=True)
class SaltMasterFactory(SaltDaemonFactory):

    factories_manager = attr.ib(repr=False, hash=False, default=None)

    @staticmethod
    def default_config(
        root_dir, master_id, config_defaults=None, config_overrides=None, order_masters=False,
    ):
        if config_defaults is None:
            config_defaults = salt.config.DEFAULT_MASTER_OPTS.copy()
            config_defaults.pop("user", None)

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

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        yield self.config["id"], "salt/master/{id}/start".format(**self.config)

    # The following methods just route the calls to the right method in the factories manager
    # while making sure the CLI tools are referring to this daemon
    def configure_salt_master(self, request, master_id, **kwargs):
        """
        This method will configure a master under a master-of-masters.

        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.configure_salt_master`
        """
        return self.factories_manager.configure_salt_master(
            request, master_id, master_of_masters_id=self.id, **kwargs
        )

    def spawn_salt_master(self, request, master_id, **kwargs):
        """
        This method will configure a master under a master-of-masters.

        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.spawn_salt_master`
        """
        return self.factories_manager.spawn_salt_master(
            request, master_id, master_of_masters_id=self.id, **kwargs
        )

    def configure_salt_minion(self, request, minion_id, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.configure_salt_minion`
        """
        return self.factories_manager.configure_salt_minion(
            request, minion_id, master_id=self.id, **kwargs
        )

    def spawn_salt_minion(self, request, minion_id, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.spawn_salt_minion`
        """
        return self.factories_manager.spawn_salt_minion(
            request, minion_id, master_id=self.id, **kwargs
        )

    def configure_salt_proxy_minion(self, request, minion_id, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.configure_salt_proxy_minion`
        """
        return self.factories_manager.configure_salt_proxy_minion(
            request, minion_id, master_id=self.id, **kwargs
        )

    def spawn_salt_proxy_minion(self, request, minion_id, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.spawn_salt_proxy_minion`
        """
        return self.factories_manager.spawn_salt_proxy_minion(
            request, minion_id, master_id=self.id, **kwargs
        )

    def configure_salt_api(self, request, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.configure_salt_api`
        """
        return self.factories_manager.configure_salt_api(request, self.id, **kwargs)

    def spawn_salt_api(self, request, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.spawn_salt_api`
        """
        return self.factories_manager.spawn_salt_api(request, self.id, **kwargs)

    def configure_salt_syndic(self, request, syndic_id, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.configure_salt_syndic`
        """
        return self.factories_manager.configure_salt_syndic(
            request, syndic_id, master_of_masters_id=self.id, **kwargs
        )

    def spawn_salt_syndic(self, request, syndic_id, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.spawn_salt_syndic`
        """
        return self.factories_manager.spawn_salt_syndic(
            request, syndic_id, master_of_masters_id=self.id, **kwargs
        )

    def configure_salt_cloud(self, request, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.configure_salt_cloud`
        """
        return self.factories_manager.configure_salt_cloud(request, self.id, **kwargs)

    def get_salt_cloud_cli(self, request, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.get_salt_cloud_cli`
        """
        return self.factories_manager.get_salt_cloud_cli(request, self.id, **kwargs)

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
