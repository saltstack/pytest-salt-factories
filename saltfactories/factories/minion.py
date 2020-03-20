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
        root_dir, minion_id, default_options=None, config_overrides=None, master_port=None
    ):
        if default_options is None:
            default_options = salt.config.DEFAULT_MINION_OPTS.copy()

        conf_dir = root_dir.join("conf").ensure(dir=True)
        conf_file = conf_dir.join("minion").strpath

        stop_sending_events_file = conf_dir.join("stop-sending-events-{}".format(minion_id)).strpath
        with salt.utils.files.fopen(stop_sending_events_file, "w") as wfh:
            wfh.write("")

        _default_options = {
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
            "open_mode": True,
            #'multiprocessing': False,
            "log_fmt_console": "%(asctime)s,%(msecs)03.0f [%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
            "log_fmt_logfile": "[%(asctime)s,%(msecs)03.0f][%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
            "hash_type": "sha256",
            "transport": "zeromq",
            "pytest-minion": {"log": {"prefix": "salt-minion({})".format(minion_id)},},
        }
        # Merge in the initial default options with the internal _default_options
        salt.utils.dictupdate.update(default_options, _default_options, merge_lists=True)

        if config_overrides:
            # Merge in the default options with the minion_config_overrides
            salt.utils.dictupdate.update(default_options, config_overrides, merge_lists=True)

        return default_options
