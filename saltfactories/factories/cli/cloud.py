"""
..
    PYTEST_DONT_REWRITE


saltfactories.factories.daemons.master
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Salt Master Factory
"""
import logging
import pathlib
import pprint
import urllib.parse

import attr
import salt.config
import salt.utils.dictupdate
import salt.utils.files
import salt.utils.yaml

from saltfactories.factories.base import SaltCliFactory
from saltfactories.utils import running_username

log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True)
class SaltCloudFactory(SaltCliFactory):
    @staticmethod
    def default_config(root_dir, master_id, config_defaults=None, config_overrides=None):
        if config_defaults is None:
            config_defaults = {}

        conf_dir = root_dir / "conf"
        conf_dir.mkdir(parents=True, exist_ok=True)
        for confd in ("cloud.conf.d", "cloud.providers.d", "cloud.profiles.d"):
            dpath = conf_dir / confd
            dpath.mkdir(exist_ok=True)

        conf_file = str(conf_dir / "cloud")

        _config_defaults = {
            "conf_file": conf_file,
            "root_dir": str(root_dir),
            "log_file": "logs/cloud.log",
            "log_level_logfile": "debug",
            "pytest-cloud": {
                "master-id": master_id,
                "log": {"prefix": "{{cli_name}}({})".format(master_id)},
            },
        }
        # Merge in the initial default options with the internal _config_defaults
        salt.utils.dictupdate.update(config_defaults, _config_defaults, merge_lists=True)

        if config_overrides:
            # Merge in the default options with the master_config_overrides
            salt.utils.dictupdate.update(config_defaults, config_overrides, merge_lists=True)

        return config_defaults

    @classmethod
    def configure(
        cls,
        factories_manager,
        daemon_id,
        root_dir=None,
        config_defaults=None,
        config_overrides=None,
        **configure_kwargs
    ):
        return cls.default_config(
            root_dir, daemon_id, config_defaults=config_defaults, config_overrides=config_overrides
        )

    @classmethod
    def verify_config(cls, config):
        prepend_root_dirs = []
        for config_key in ("log_file",):
            if urllib.parse.urlparse(config.get(config_key, "")).scheme == "":
                prepend_root_dirs.append(config_key)
        if prepend_root_dirs:
            salt.config.prepend_root_dir(config, prepend_root_dirs)
        salt.utils.verify.verify_env(
            [str(pathlib.Path(config["log_file"]).parent)],
            running_username(),
            pki_dir=config.get("pki_dir") or "",
            root_dir=config["root_dir"],
        )

    @classmethod
    def write_config(cls, config):
        cls.verify_config(config)
        config_file = config.pop("conf_file")
        log.debug(
            "Writing to configuration file %s. Configuration:\n%s",
            config_file,
            pprint.pformat(config),
        )

        # Write down the computed configuration into the config file
        with salt.utils.files.fopen(config_file, "w") as wfh:
            salt.utils.yaml.safe_dump(config, wfh, default_flow_style=False)
        return salt.config.cloud_config(config_file)
