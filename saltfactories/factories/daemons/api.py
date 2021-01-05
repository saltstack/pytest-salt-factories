"""
..
    PYTEST_DONT_REWRITE


saltfactories.factories.daemons.api
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Salt API Factory
"""
import attr

from saltfactories.factories.base import SaltDaemonFactory


@attr.s(kw_only=True, slots=True)
class SaltApiFactory(SaltDaemonFactory):
    def __attrs_post_init__(self):
        if "rest_cherrypy" in self.config:
            self.check_ports = [self.config["rest_cherrypy"]["port"]]
        elif "rest_tornado" in self.config:
            self.check_ports = [self.config["rest_tornado"]["port"]]
        else:
            raise RuntimeError(
                "The salt-master configuration for this salt-api instance does not seem to have "
                "any api properly configured."
            )
        super().__attrs_post_init__()

    @classmethod
    def _configure(
        cls,
        factories_manager,
        daemon_id,
        root_dir=None,
        config_defaults=None,
        config_overrides=None,
    ):
        raise RuntimeError(
            "The salt-api daemon is not configurable. It uses the salt-master config that "
            "it's attached to."
        )

    @classmethod
    def _get_verify_config_entries(cls, config):
        return []

    @classmethod
    def load_config(cls, config_file, config):
        raise RuntimeError(
            "The salt-api daemon does not have it's own config file. It uses the salt-master config that "
            "it's attached to."
        )

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        return []
