"""
..
    PYTEST_DONT_REWRITE


saltfactories.factories.daemons.master
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Salt Master Factory
"""
import pathlib
import shutil
from functools import partial

import attr
import salt.config
import salt.utils.dictupdate

from saltfactories.factories import cli
from saltfactories.factories.base import SaltDaemonFactory
from saltfactories.utils import cli_scripts
from saltfactories.utils import ports
from saltfactories.utils import running_username


@attr.s(kw_only=True, slots=True)
class SaltMasterFactory(SaltDaemonFactory):
    on_auth_event_callback = attr.ib(repr=False, default=None)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.config.get("open_mode", False) is False:
            # If the master is not configured to be in open mode, register an auth event callback
            # If we were passed an auth event callback, it needs to get this master as the first
            # argument
            if self.on_auth_event_callback:
                auth_event_callback = partial(self.on_auth_event_callback, self)
            else:
                auth_event_callback = self._on_auth_event
            self.register_before_start_callback(
                self.event_listener.register_auth_event_handler, self.id, auth_event_callback
            )
            self.register_after_terminate_callback(
                self.event_listener.unregister_auth_event_handler, self.id
            )

    @classmethod
    def default_config(
        cls,
        root_dir,
        master_id,
        config_defaults=None,
        config_overrides=None,
        order_masters=False,
        master_of_masters=None,
        system_install=False,
    ):
        if config_defaults is None:
            config_defaults = {}

        if config_overrides is None:
            config_overrides = {}
        else:
            config_overrides = config_overrides.copy()
        master_of_masters_id = None
        if master_of_masters:
            master_of_masters_id = master_of_masters.id
            config_overrides["syndic_master"] = master_of_masters.config["interface"]
            config_overrides["syndic_master_port"] = master_of_masters.config["ret_port"]
            # Match transport if not set
            config_defaults.setdefault("transport", master_of_masters.config["transport"])

        if system_install is True:

            conf_dir = root_dir / "etc" / "salt"
            conf_dir.mkdir(parents=True, exist_ok=True)
            conf_file = str(conf_dir / "master")
            pki_dir = conf_dir / "pki" / "master"

            logs_dir = root_dir / "var" / "log" / "salt"
            logs_dir.mkdir(parents=True, exist_ok=True)

            pidfile_dir = root_dir / "var" / "run"

            state_tree_root = root_dir / "srv" / "salt"
            state_tree_root.mkdir(parents=True, exist_ok=True)
            pillar_tree_root = root_dir / "srv" / "pillar"
            pillar_tree_root.mkdir(parents=True, exist_ok=True)

            _config_defaults = {
                "id": master_id,
                "conf_file": conf_file,
                "root_dir": str(root_dir),
                "interface": "127.0.0.1",
                "publish_port": salt.config.DEFAULT_MASTER_OPTS["publish_port"],
                "ret_port": salt.config.DEFAULT_MASTER_OPTS["ret_port"],
                "tcp_master_pub_port": salt.config.DEFAULT_MASTER_OPTS["tcp_master_pub_port"],
                "tcp_master_pull_port": salt.config.DEFAULT_MASTER_OPTS["tcp_master_pull_port"],
                "tcp_master_publish_pull": salt.config.DEFAULT_MASTER_OPTS[
                    "tcp_master_publish_pull"
                ],
                "tcp_master_workers": salt.config.DEFAULT_MASTER_OPTS["tcp_master_workers"],
                "api_pidfile": str(pidfile_dir / "api.pid"),
                "pki_dir": str(pki_dir),
                "fileserver_backend": ["roots"],
                "log_file": str(logs_dir / "master.log"),
                "log_level_logfile": "debug",
                "api_logfile": str(logs_dir / "api.log"),
                "key_logfile": str(logs_dir / "key.log"),
                "log_fmt_console": "%(asctime)s,%(msecs)03.0f [%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
                "log_fmt_logfile": "[%(asctime)s,%(msecs)03.0f][%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
                "file_roots": {
                    "base": [str(state_tree_root)],
                },
                "pillar_roots": {
                    "base": [str(pillar_tree_root)],
                },
                "order_masters": order_masters,
                "max_open_files": 10240,
                "pytest-master": {
                    "master-id": master_of_masters_id,
                    "log": {"prefix": "{}(id={!r})".format(cls.__name__, master_id)},
                },
            }
        else:
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
                "pidfile": "run/master.pid",
                "api_pidfile": "run/api.pid",
                "pki_dir": "pki",
                "cachedir": "cache",
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
                "file_roots": {
                    "base": [str(state_tree_root_base)],
                    "prod": [str(state_tree_root_prod)],
                },
                "pillar_roots": {
                    "base": [str(pillar_tree_root_base)],
                    "prod": [str(pillar_tree_root_prod)],
                },
                "order_masters": order_masters,
                "max_open_files": 10240,
                "enable_legacy_startup_events": False,
                "pytest-master": {
                    "master-id": master_of_masters_id,
                    "log": {"prefix": "{}(id={!r})".format(cls.__name__, master_id)},
                },
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
        master_of_masters=None,
        root_dir=None,
        config_defaults=None,
        config_overrides=None,
        order_masters=False,
    ):
        return cls.default_config(
            root_dir,
            daemon_id,
            master_of_masters=master_of_masters,
            config_defaults=config_defaults,
            config_overrides=config_overrides,
            order_masters=order_masters,
            system_install=factories_manager.system_install,
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
        verify_env_entries.extend(config["file_roots"]["base"])
        if "prod" in config["file_roots"]:
            verify_env_entries.extend(config["file_roots"]["prod"])
        verify_env_entries.extend(config["pillar_roots"]["base"])
        if "prod" in config["pillar_roots"]:
            verify_env_entries.extend(config["pillar_roots"]["prod"])
        return verify_env_entries

    @classmethod
    def load_config(cls, config_file, config):
        return salt.config.master_config(config_file)

    def _on_auth_event(self, payload):
        if self.config["open_mode"]:
            return
        minion_id = payload["id"]
        keystate = payload["act"]
        salt_key_cli = self.get_salt_key_cli()
        if keystate == "pend":
            ret = salt_key_cli.run("--yes", "--accept", minion_id)
            assert ret.exitcode == 0

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
            master_id, master_of_masters=self, **kwargs
        )

    def get_salt_minion_daemon(self, minion_id, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.configure_salt_minion`
        """
        return self.factories_manager.get_salt_minion_daemon(minion_id, master=self, **kwargs)

    def get_salt_proxy_minion_daemon(self, minion_id, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.get_salt_proxy_minion_daemon`
        """
        return self.factories_manager.get_salt_proxy_minion_daemon(minion_id, master=self, **kwargs)

    def get_salt_api_daemon(self, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.get_salt_api_daemon`
        """
        return self.factories_manager.get_salt_api_daemon(self, **kwargs)

    def get_salt_syndic_daemon(self, syndic_id, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.get_salt_syndic_daemon`
        """
        return self.factories_manager.get_salt_syndic_daemon(
            syndic_id, master_of_masters=self, **kwargs
        )

    def get_salt_cloud_cli(
        self,
        config_defaults=None,
        config_overrides=None,
        factory_class=cli.cloud.SaltCloudFactory,
        **factory_class_kwargs
    ):
        """
        Return a salt-cloud CLI instance

        Args:
            config_defaults(dict):
                A dictionary of default configuration to use when configuring the minion
            config_overrides(dict):
                A dictionary of configuration overrides to use when configuring the minion

        Returns:
            :py:class:`~saltfactories.factories.cli.cloud.SaltCloudFactory`:
                The salt-cloud CLI script process class instance
        """

        root_dir = pathlib.Path(self.config["root_dir"])

        config = factory_class.configure(
            self,
            self.id,
            root_dir=root_dir,
            config_defaults=config_defaults,
            config_overrides=config_overrides,
        )
        self.factories_manager.final_cloud_config_tweaks(config)
        config = factory_class.write_config(config)

        if self.system_install is False:
            script_path = cli_scripts.generate_script(
                self.factories_manager.scripts_dir,
                "salt-cloud",
                code_dir=self.factories_manager.code_dir,
                inject_coverage=self.factories_manager.inject_coverage,
                inject_sitecustomize=self.factories_manager.inject_sitecustomize,
            )
        else:
            script_path = shutil.which("salt-cloud")
        return factory_class(
            cli_script_name=script_path,
            config=config,
            system_install=self.factories_manager.system_install,
            **factory_class_kwargs
        )

    def get_salt_cli(self, factory_class=cli.salt.SaltCliFactory, **factory_class_kwargs):
        """
        Return a `salt` CLI process for this master instance
        """
        if self.system_install is False:
            script_path = cli_scripts.generate_script(
                self.factories_manager.scripts_dir,
                "salt",
                code_dir=self.factories_manager.code_dir,
                inject_coverage=self.factories_manager.inject_coverage,
                inject_sitecustomize=self.factories_manager.inject_sitecustomize,
            )
        else:
            script_path = shutil.which("salt")
        return factory_class(
            cli_script_name=script_path,
            config=self.config.copy(),
            system_install=self.factories_manager.system_install,
            **factory_class_kwargs
        )

    def get_salt_cp_cli(self, factory_class=cli.cp.SaltCpCliFactory, **factory_class_kwargs):
        """
        Return a `salt-cp` CLI process for this master instance
        """
        if self.system_install is False:
            script_path = cli_scripts.generate_script(
                self.factories_manager.scripts_dir,
                "salt-cp",
                code_dir=self.factories_manager.code_dir,
                inject_coverage=self.factories_manager.inject_coverage,
                inject_sitecustomize=self.factories_manager.inject_sitecustomize,
            )
        else:
            script_path = shutil.which("salt-cp")
        return factory_class(
            cli_script_name=script_path,
            config=self.config.copy(),
            system_install=self.factories_manager.system_install,
            **factory_class_kwargs
        )

    def get_salt_key_cli(self, factory_class=cli.key.SaltKeyCliFactory, **factory_class_kwargs):
        """
        Return a `salt-key` CLI process for this master instance
        """
        if self.system_install is False:
            script_path = cli_scripts.generate_script(
                self.factories_manager.scripts_dir,
                "salt-key",
                code_dir=self.factories_manager.code_dir,
                inject_coverage=self.factories_manager.inject_coverage,
                inject_sitecustomize=self.factories_manager.inject_sitecustomize,
            )
        else:
            script_path = shutil.which("salt-key")
        return factory_class(
            cli_script_name=script_path,
            config=self.config.copy(),
            system_install=self.factories_manager.system_install,
            **factory_class_kwargs
        )

    def get_salt_run_cli(self, factory_class=cli.run.SaltRunCliFactory, **factory_class_kwargs):
        """
        Return a `salt-run` CLI process for this master instance
        """
        if self.system_install is False:
            script_path = cli_scripts.generate_script(
                self.factories_manager.scripts_dir,
                "salt-run",
                code_dir=self.factories_manager.code_dir,
                inject_coverage=self.factories_manager.inject_coverage,
                inject_sitecustomize=self.factories_manager.inject_sitecustomize,
            )
        else:
            script_path = shutil.which("salt-run")
        return factory_class(
            cli_script_name=script_path,
            config=self.config.copy(),
            system_install=self.factories_manager.system_install,
            **factory_class_kwargs
        )

    def get_salt_spm_cli(self, factory_class=cli.spm.SpmCliFactory, **factory_class_kwargs):
        """
        Return a `spm` CLI process for this master instance
        """
        if self.system_install is False:
            script_path = cli_scripts.generate_script(
                self.factories_manager.scripts_dir,
                "spm",
                code_dir=self.factories_manager.code_dir,
                inject_coverage=self.factories_manager.inject_coverage,
                inject_sitecustomize=self.factories_manager.inject_sitecustomize,
            )
        else:
            script_path = shutil.which("spm")
        return factory_class(
            cli_script_name=script_path,
            config=self.config.copy(),
            system_install=self.factories_manager.system_install,
            **factory_class_kwargs
        )

    def get_salt_ssh_cli(
        self,
        factory_class=cli.ssh.SaltSshCliFactory,
        roster_file=None,
        target_host=None,
        client_key=None,
        ssh_user=None,
        **factory_class_kwargs
    ):
        """
        Return a `salt-ssh` CLI process for this master instance

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
        if self.system_install is False:
            script_path = cli_scripts.generate_script(
                self.factories_manager.scripts_dir,
                "salt-ssh",
                code_dir=self.factories_manager.code_dir,
                inject_coverage=self.factories_manager.inject_coverage,
                inject_sitecustomize=self.factories_manager.inject_sitecustomize,
            )
        else:
            script_path = shutil.which("salt-ssh")
        return factory_class(
            cli_script_name=script_path,
            config=self.config.copy(),
            roster_file=roster_file,
            target_host=target_host,
            client_key=client_key,
            ssh_user=ssh_user or running_username(),
            system_install=self.factories_manager.system_install,
            **factory_class_kwargs
        )

    def get_salt_client(
        self,
        functions_known_to_return_none=None,
        factory_class=cli.client.SaltClientFactory,
    ):
        """
        Return a local salt client object
        """
        return factory_class(
            master_config=self.config.copy(),
            functions_known_to_return_none=functions_known_to_return_none,
        )
