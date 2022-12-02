"""
``spm`` CLI factory.
"""
import logging
import pathlib
import pprint
import urllib.parse

import attr

from saltfactories.bases import SaltCli
from saltfactories.utils import running_username

log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True)
class Spm(SaltCli):
    """
    ``spm`` CLI factory.
    """

    __cli_output_supported__ = attr.ib(repr=False, init=False, default=False)

    def get_minion_tgt(self, minion_tgt=None):
        """
        Overridden method because spm does not target minions.
        """
        return None

    @staticmethod
    def default_config(root_dir, master_factory, defaults=None, overrides=None):
        """
        Return the default configuration for the daemon.
        """
        import salt.utils.dictupdate

        if defaults is None:
            defaults = {}

        master_conf_dir = pathlib.Path(master_factory.config_dir)
        conf_dir = master_conf_dir / "master.d"
        conf_dir.mkdir(parents=True, exist_ok=True)
        conf_file = str(conf_dir / "spm.conf")

        _defaults = {
            "spm_conf_file": conf_file,
            "root_dir": str(root_dir),
            "formula_path": "srv/formulas",
            "pillar_path": "srv/pillar",
            "reactor_path": "src/reactor",
            "spm_repos_config": str(master_conf_dir / "spm.repos"),
            "spm_cache_dir": "cache/spm",
            "spm_build_dir": "srv/spm_build",
            "spm_db": "cache/spm/packages.db",
            "spm_share_dir": "share/spm",
            "spm_logfile": "logs/spm.log",
            "spm_log_level_logfile": "debug",
            "pytest-spm": {
                "master-id": master_factory.id,
                "log": {"prefix": "{{cli_name}}({})".format(master_factory.id)},
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
        master_factory,
        root_dir=None,
        defaults=None,
        overrides=None,
    ):
        """
        Configure the CLI.
        """
        return cls.default_config(root_dir, master_factory, defaults=defaults, overrides=overrides)

    @classmethod
    def verify_config(cls, config):
        """
        Verify the configuration dictionary.
        """
        import salt.config
        import salt.utils.verify

        prepend_root_dirs = [
            "formula_path",
            "pillar_path",
            "reactor_path",
            "spm_db",
            "spm_cache_dir",
            "spm_build_dir",
            "spm_share_dir",
        ]
        for config_key in ("spm_logfile",):
            if urllib.parse.urlparse(config.get(config_key, "")).scheme == "":
                prepend_root_dirs.append(config_key)
        if prepend_root_dirs:
            salt.config.prepend_root_dir(config, prepend_root_dirs)
        salt.utils.verify.verify_env(
            [
                str(pathlib.Path(config["spm_logfile"]).parent),
                str(pathlib.Path(config["spm_db"]).parent),
                config["formula_path"],
                config["pillar_path"],
                config["reactor_path"],
                config["spm_cache_dir"],
                config["spm_build_dir"],
                config["spm_share_dir"],
            ],
            running_username(),
            pki_dir=config.get("pki_dir") or "",
            root_dir=config["root_dir"],
        )

    @classmethod
    def write_config(cls, config):
        """
        Verify the loaded configuration.
        """
        import salt.config
        import salt.utils.verify

        cls.verify_config(config)
        config_file = config.pop("spm_conf_file")
        log.debug(
            "Writing to configuration file %s. Configuration:\n%s",
            config_file,
            pprint.pformat(config),
        )

        # Write down the computed configuration into the config file
        with salt.utils.files.fopen(config_file, "w") as wfh:
            salt.utils.yaml.safe_dump(config, wfh, default_flow_style=False)
        # We load the master config, which will include the spm config
        return salt.config.spm_config(
            str(pathlib.Path(config_file).parent.parent / "master"),
        )
