"""
..
    PYTEST_DONT_REWRITE


saltfactories.factories.daemons.proxy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Salt Proxy Minion Factory
"""
import logging
import pathlib
import sys

import attr
import salt.config
import salt.utils.dictupdate
import salt.utils.files

from saltfactories.factories.base import SaltDaemonFactory
from saltfactories.utils import ports

log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True)
class SaltProxyMinionFactory(SaltDaemonFactory):

    include_proxyid_cli_flag = attr.ib(default=True, repr=False)

    @staticmethod
    def default_config(
        root_dir, proxy_minion_id, config_defaults=None, config_overrides=None, master_port=None,
    ):
        if config_defaults is None:
            config_defaults = {}

        conf_dir = root_dir / "conf"
        conf_dir.mkdir(parents=True, exist_ok=True)
        conf_file = str(conf_dir / "proxy")

        _config_defaults = {
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
            #'multiprocessing': False,
            "log_fmt_console": "%(asctime)s,%(msecs)03.0f [%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
            "log_fmt_logfile": "[%(asctime)s,%(msecs)03.0f][%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
            "hash_type": "sha256",
            "transport": "zeromq",
            "add_proxymodule_to_opts": False,
            "proxy": {"proxytype": "dummy"},
            "pytest-minion": {"log": {"prefix": "{{cli_name}}({})".format(proxy_minion_id)},},
        }
        # Merge in the initial default options with the internal _config_defaults
        salt.utils.dictupdate.update(config_defaults, _config_defaults, merge_lists=True)

        if config_overrides:
            # Merge in the default options with the proxy_config_overrides
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
        master_id=None,
    ):
        master = master_port = None
        if master_id is not None:
            master = factories_manager.cache["masters"].get(master_id)
            if master:
                master_port = master.config.get("ret_port")
        config = cls.default_config(
            root_dir,
            daemon_id,
            config_defaults=config_defaults,
            config_overrides=config_overrides,
            master_port=master_port,
        )
        if master is not None:
            # The in-memory minion config dictionary will hold a copy of the master config
            # in order to listen to start events so that we can confirm the proxy-minion is up, running
            # and accepting requests
            config["pytest-minion"]["master_config"] = master.config
        return config

    @classmethod
    def _get_verify_config_entries(cls, config):
        # verify env to make sure all required directories are created and have the
        # right permissions
        pki_dir = pathlib.Path(config["pki_dir"])
        return [
            str(pathlib.Path(config["log_file"]).parent),
            # config['extension_modules'],
            config["sock_dir"],
        ]

    @classmethod
    def load_config(cls, config_file, config):
        return salt.config.proxy_config(config_file, minion_id=config["id"], cache_minion_id=True)

    def get_base_script_args(self):
        script_args = super().get_base_script_args()
        if sys.platform.startswith("win") is False:
            script_args.append("--disable-keepalive")
        if self.include_proxyid_cli_flag is True:
            script_args.extend(["--proxyid", self.id])
        return script_args

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

    # The following methods just route the calls to the right method in the factories manager
    # while making sure the CLI tools are referring to this daemon
    def get_salt_call_cli(self, **kwargs):
        """
        Please see the documentation in :py:class:`~saltfactories.factories.manager.FactoriesManager.get_salt_call_cli`
        """
        return self.factories_manager.get_salt_call_cli(self.id, **kwargs)
