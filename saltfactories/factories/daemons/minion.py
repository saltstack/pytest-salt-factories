"""
..
    PYTEST_DONT_REWRITE


saltfactories.factories.daemons.minion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Minion Factory
"""
import sys

import attr
import salt.config
import salt.utils.dictupdate
import salt.utils.files

from saltfactories.factories.base import SaltDaemonFactory
from saltfactories.utils import ports


@attr.s(kw_only=True, slots=True)
class MinionFactory(SaltDaemonFactory):
    @staticmethod
    def default_config(
        root_dir, minion_id, config_defaults=None, config_overrides=None, master_port=None
    ):
        if config_defaults is None:
            config_defaults = salt.config.DEFAULT_MINION_OPTS.copy()
            config_defaults.pop("user", None)

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
            #'multiprocessing': False,
            "log_fmt_console": "%(asctime)s,%(msecs)03.0f [%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
            "log_fmt_logfile": "[%(asctime)s,%(msecs)03.0f][%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
            "hash_type": "sha256",
            "transport": "zeromq",
            "pytest-minion": {"log": {"prefix": "{{cli_name}}({})".format(minion_id)},},
            "acceptance_wait_time": 0.5,
            "acceptance_wait_time_max": 5,
        }
        # Merge in the initial default options with the internal _config_defaults
        salt.utils.dictupdate.update(config_defaults, _config_defaults, merge_lists=True)

        if config_overrides:
            # Merge in the default options with the minion_config_overrides
            salt.utils.dictupdate.update(config_defaults, config_overrides, merge_lists=True)

        return config_defaults

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
        yield pytest_config["master_config"]["id"], "salt/{__role}/{id}/start".format(**self.config)
