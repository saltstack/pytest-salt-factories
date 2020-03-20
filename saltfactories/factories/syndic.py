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


class SyndicFactory(object):
    @staticmethod
    def default_config(
        root_dir,
        syndic_id,
        default_options=None,
        config_overrides=None,
        master_port=None,
        syndic_master_port=None,
    ):
        if default_options is None:
            # default_options = {"syndic": salt.config.syndic_config(None, None)}
            # We don't really want the whole default config dictionary
            default_options = {"syndic": {}}

        if config_overrides is None:
            config_overrides = {}

        conf_dir = root_dir.join("conf").ensure(dir=True)
        conf_d_dir = conf_dir.join("master.d").ensure(dir=True)
        conf_file = conf_d_dir.join("syndic.conf").strpath

        master_config = SyndicFactory.default_master_config(
            root_dir,
            conf_dir,
            syndic_id,
            default_options=default_options.get("master"),
            config_overrides=config_overrides.get("master"),
        )
        minion_config = SyndicFactory.default_minion_config(
            root_dir,
            conf_dir,
            syndic_id,
            default_options=default_options.get("minion"),
            config_overrides=config_overrides.get("minion"),
            master_port=master_config["ret_port"],
        )

        stop_sending_events_file = conf_dir.join(
            "stop-sending-events-{}-syndic".format(syndic_id)
        ).strpath
        with salt.utils.files.fopen(stop_sending_events_file, "w") as wfh:
            wfh.write("")

        _default_options = {
            "id": syndic_id,
            "master_id": syndic_id,
            "conf_file": conf_file,
            "root_dir": root_dir.strpath,
            "syndic_master": "127.0.0.1",
            "syndic_master_port": syndic_master_port or ports.get_unused_localhost_port(),
            "syndic_pidfile": "run/syndic.pid",
            "syndic_log_file": "logs/syndic.log",
            "syndic_log_level_logfile": "debug",
            "syndic_dir": "cache/syndics",
            "pytest-syndic": {"log": {"prefix": "salt-syndic({})".format(syndic_id)},},
        }
        # Merge in the initial default options with the internal _default_options
        salt.utils.dictupdate.update(
            default_options.get("syndic"), _default_options, merge_lists=True
        )

        if config_overrides.get("syndic"):
            # Merge in the default options with the syndic_config_overrides
            salt.utils.dictupdate.update(
                default_options.get("syndic"), config_overrides.get("syndic"), merge_lists=True
            )

        return {
            "master": master_config,
            "minion": minion_config,
            "syndic": default_options["syndic"],
        }

    @staticmethod
    def default_minion_config(
        root_dir, conf_dir, minion_id, default_options=None, config_overrides=None, master_port=None
    ):
        if default_options is None:
            default_options = salt.config.DEFAULT_MINION_OPTS.copy()
            default_options = {}

        conf_file = conf_dir.join("minion").strpath

        stop_sending_events_file = conf_dir.join(
            "stop-sending-events-{}-minion".format(minion_id)
        ).strpath
        with salt.utils.files.fopen(stop_sending_events_file, "w") as wfh:
            wfh.write("")

        _default_options = {
            "id": minion_id,
            "master_id": minion_id,
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

    @staticmethod
    def default_master_config(
        root_dir, conf_dir, master_id, default_options=None, config_overrides=None,
    ):
        if default_options is None:
            default_options = salt.config.DEFAULT_MASTER_OPTS.copy()
            default_options = {}

        conf_file = conf_dir.join("master").strpath
        state_tree_root = root_dir.join("state-tree").ensure(dir=True)
        state_tree_root_base = state_tree_root.join("base").ensure(dir=True).strpath
        state_tree_root_prod = state_tree_root.join("prod").ensure(dir=True).strpath
        pillar_tree_root = root_dir.join("pillar-tree").ensure(dir=True)
        pillar_tree_root_base = pillar_tree_root.join("base").ensure(dir=True).strpath
        pillar_tree_root_prod = pillar_tree_root.join("prod").ensure(dir=True).strpath

        stop_sending_events_file = conf_dir.join(
            "stop-sending-events-{}-master".format(master_id)
        ).strpath
        with salt.utils.files.fopen(stop_sending_events_file, "w") as wfh:
            wfh.write("")

        _default_options = {
            "id": master_id,
            "master_id": master_id,
            "conf_file": conf_file,
            "root_dir": root_dir.strpath,
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
            "token_file": root_dir.join("ksfjhdgiuebfgnkefvsikhfjdgvkjahcsidk").strpath,
            "file_buffer_size": 8192,
            "log_fmt_console": "%(asctime)s,%(msecs)03.0f [%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
            "log_fmt_logfile": "[%(asctime)s,%(msecs)03.0f][%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
            "file_roots": {"base": state_tree_root_base, "prod": state_tree_root_prod},
            "pillar_roots": {"base": pillar_tree_root_base, "prod": pillar_tree_root_prod},
            "hash_type": "sha256",
            "transport": "zeromq",
            "order_masters": False,
            "max_open_files": 10240,
            "pytest-master": {"log": {"prefix": "salt-master({})".format(master_id)},},
        }
        # Merge in the initial default options with the internal _default_options
        salt.utils.dictupdate.update(default_options, _default_options, merge_lists=True)

        if config_overrides:
            # Merge in the default options with the master_config_overrides
            salt.utils.dictupdate.update(default_options, config_overrides, merge_lists=True)

        # Remove syndic related options
        for key in list(default_options):
            if key.startswith("syndic_"):
                default_options.pop(key)

        return default_options
