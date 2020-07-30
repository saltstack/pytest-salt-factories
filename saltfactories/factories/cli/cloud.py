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

from saltfactories.factories.base import SaltCliFactory


@attr.s(kw_only=True, slots=True)
class SaltCloudFactory(SaltCliFactory):
    @staticmethod
    def default_config(root_dir, master_id, config_defaults=None, config_overrides=None):
        if config_defaults is None:
            config_defaults = salt.config.DEFAULT_CLOUD_OPTS.copy()
            config_defaults.pop("user", None)

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
            "pytest-cloud": {"log": {"prefix": "{{cli_name}}({})".format(master_id)},},
        }
        # Merge in the initial default options with the internal _config_defaults
        salt.utils.dictupdate.update(config_defaults, _config_defaults, merge_lists=True)

        if config_overrides:
            # Merge in the default options with the master_config_overrides
            salt.utils.dictupdate.update(config_defaults, config_overrides, merge_lists=True)

        return config_defaults
