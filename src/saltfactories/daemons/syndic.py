"""
Salt Syndic Factory.

..
    PYTEST_DONT_REWRITE
"""
import logging
import pathlib

import attr
import salt.config
import salt.utils.dictupdate
from pytestshellutils.utils import ports

from saltfactories.bases import SaltDaemon

log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True)
class SaltSyndic(SaltDaemon):
    """
    salt-syndic daemon factory.
    """

    master = attr.ib(repr=False, hash=False)
    minion = attr.ib(repr=False, hash=False)

    @classmethod
    def default_config(
        cls,
        root_dir,
        syndic_id,
        defaults=None,
        overrides=None,
        master_of_masters=None,
        system_install=False,
    ):
        """
        Return the default configuration.
        """
        if defaults is None:
            defaults = {}

        if overrides is None:
            overrides = {}

        master_of_masters_id = syndic_master_port = None
        if master_of_masters:
            master_of_masters_id = master_of_masters.id
            syndic_master_port = master_of_masters.config["ret_port"]
            # Match transport if not set
            defaults.setdefault("transport", master_of_masters.config["transport"])

        if system_install is True:
            conf_dir = root_dir / "etc" / "salt"
            conf_dir.mkdir(parents=True, exist_ok=True)
            conf_d_dir = conf_dir / "master.d"
            conf_d_dir.mkdir(exist_ok=True)
            conf_file = str(conf_d_dir / "syndic.conf")

            pidfile_dir = root_dir / "var" / "run"

            logs_dir = root_dir / "var" / "log" / "salt"
            logs_dir.mkdir(parents=True, exist_ok=True)

            _defaults = {
                "id": syndic_id,
                "master_id": syndic_id,
                "conf_file": conf_file,
                "root_dir": str(root_dir),
                "syndic_master": "127.0.0.1",
                "syndic_master_port": syndic_master_port
                or salt.config.DEFAULT_MASTER_OPTS["ret_port"],
                "syndic_pidfile": str(pidfile_dir / "syndic.pid"),
                "syndic_log_file": str(logs_dir / "syndic.log"),
                "syndic_log_level_logfile": "debug",
                "pytest-syndic": {
                    "master-id": master_of_masters_id,
                    "log": {"prefix": "{}(id={!r})".format(cls.__name__, syndic_id)},
                },
            }
        else:
            conf_dir = root_dir / "conf"
            conf_dir.mkdir(parents=True, exist_ok=True)
            conf_d_dir = conf_dir / "master.d"
            conf_d_dir.mkdir(exist_ok=True)
            conf_file = str(conf_d_dir / "syndic.conf")

            _defaults = {
                "id": syndic_id,
                "master_id": syndic_id,
                "conf_file": conf_file,
                "root_dir": str(root_dir),
                "syndic_master": "127.0.0.1",
                "syndic_master_port": syndic_master_port or ports.get_unused_localhost_port(),
                "syndic_pidfile": "run/syndic.pid",
                "syndic_log_file": "logs/syndic.log",
                "syndic_log_level_logfile": "debug",
                "syndic_dir": "cache/syndics",
                "enable_legacy_startup_events": False,
                "pytest-syndic": {
                    "master-id": master_of_masters_id,
                    "log": {"prefix": "{}(id={!r})".format(cls.__name__, syndic_id)},
                },
            }
        # Merge in the initial default options with the internal _defaults
        salt.utils.dictupdate.update(defaults, _defaults, merge_lists=True)

        if overrides:
            # Merge in the default options with the syndic_overrides
            salt.utils.dictupdate.update(defaults, overrides, merge_lists=True)
        return defaults

    @classmethod
    def _configure(  # pylint: disable=arguments-differ
        cls,
        factories_manager,
        daemon_id,
        root_dir=None,
        defaults=None,
        overrides=None,
        master_of_masters=None,
    ):
        return cls.default_config(
            root_dir,
            daemon_id,
            defaults=defaults,
            overrides=overrides,
            master_of_masters=master_of_masters,
            system_install=factories_manager.system_install,
        )

    @classmethod
    def _get_verify_config_entries(cls, config):
        # verify env to make sure all required directories are created and have the
        # right permissions
        verify_env_entries = [
            str(pathlib.Path(config["syndic_log_file"]).parent),
        ]
        return verify_env_entries

    @classmethod
    def load_config(cls, config_file, config):
        """
        Return the loaded configuration.
        """
        conf_dir = pathlib.Path(config_file).parent.parent
        master_config_file = str(conf_dir / "master")
        minion_config_file = str(conf_dir / "minion")
        return salt.config.syndic_config(master_config_file, minion_config_file)

    def get_check_events(self):
        """
        Return salt events to check.

        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        pytest_config = self.config["pytest-{}".format(self.config["__role"])]
        if not pytest_config.get("master-id"):
            log.warning(
                "Will not be able to check for start events for %s since it's missing the 'master-id' key "
                "in the 'pytest-%s' dictionary, or it's value is None.",
                self,
                self.config["__role"],
            )
        else:
            yield pytest_config["master-id"], "salt/{role}/{id}/start".format(
                role=self.config["__role"], id=self.id
            )
