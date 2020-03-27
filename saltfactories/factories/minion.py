# -*- coding: utf-8 -*-
"""
saltfactories.factories.minion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Minion Factory
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

try:
    import salt.config
    import salt.utils.files
    import salt.utils.dictupdate
except ImportError:  # pragma: no cover
    # We need salt to test salt with saltfactories, and, when pytest is rewriting modules for proper assertion
    # reporting, we still haven't had a chance to inject the salt path into sys.modules, so we'll hit this
    # import error, but its safe to pass
    pass

from saltfactories.utils import ports


class MinionFactory(object):
    @staticmethod
    def default_config(
        root_dir, minion_id, config_defaults=None, config_overrides=None, master_port=None
    ):
        if config_defaults is None:
            config_defaults = salt.config.DEFAULT_MINION_OPTS.copy()
            config_defaults.pop("user", None)

        conf_dir = root_dir.join("conf").ensure(dir=True)
        conf_file = conf_dir.join("minion").strpath

        _config_defaults = {
            "id": minion_id,
            "conf_file": conf_file,
            "root_dir": root_dir.strpath,
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
            "pytest-minion": {"log": {"prefix": "salt-minion({})".format(minion_id)},},
            "acceptance_wait_time": 0.5,
            "acceptance_wait_time_max": 5,
        }
        # Merge in the initial default options with the internal _config_defaults
        salt.utils.dictupdate.update(config_defaults, _config_defaults, merge_lists=True)

        if config_overrides:
            # Merge in the default options with the minion_config_overrides
            salt.utils.dictupdate.update(config_defaults, config_overrides, merge_lists=True)

        return config_defaults
