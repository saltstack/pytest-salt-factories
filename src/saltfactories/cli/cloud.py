"""
``salt-cloud`` CLI factory.

..
    PYTEST_DONT_REWRITE
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

from saltfactories.bases import SaltCli
from saltfactories.utils import running_username

log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True)
class SaltCloud(SaltCli):
    """
    salt-cloud CLI factory.
    """

    @staticmethod
    def default_config(root_dir, master_id, defaults=None, overrides=None):
        """
        Return the default configuration for the daemon.
        """
        if defaults is None:
            defaults = {}

        conf_dir = root_dir / "conf"
        conf_dir.mkdir(parents=True, exist_ok=True)
        for confd in ("cloud.conf.d", "cloud.providers.d", "cloud.profiles.d"):
            dpath = conf_dir / confd
            dpath.mkdir(exist_ok=True)

        conf_file = str(conf_dir / "cloud")

        _defaults = {
            "conf_file": conf_file,
            "root_dir": str(root_dir),
            "log_file": "logs/cloud.log",
            "log_level_logfile": "debug",
            "pytest-cloud": {
                "master-id": master_id,
                "log": {"prefix": "{{cli_name}}({})".format(master_id)},
            },
        }
        # Merge in the initial default options with the internal _defaults
        salt.utils.dictupdate.update(defaults, _defaults, merge_lists=True)

        if overrides:
            # Merge in the default options with the master_overrides
            salt.utils.dictupdate.update(defaults, overrides, merge_lists=True)

        return defaults

    @classmethod
    def configure(
        cls,
        factories_manager,
        daemon_id,
        root_dir=None,
        defaults=None,
        overrides=None,
        **configure_kwargs
    ):
        """
        Configure the CLI.
        """
        return cls.default_config(root_dir, daemon_id, defaults=defaults, overrides=overrides)

    @classmethod
    def verify_config(cls, config):
        """
        Verify the configuration dictionary.
        """
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
        """
        Verify the loaded configuration.
        """
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
