"""
Salt API Factory.
"""
import attr
import pytest

from saltfactories.bases import SaltDaemon


@attr.s(kw_only=True, slots=True)
class SaltApi(SaltDaemon):
    """
    salt-api daemon factory.
    """

    def __attrs_post_init__(self):
        """
        Post attrs initialization routines.
        """
        if "rest_cherrypy" in self.config:
            self.check_ports = [self.config["rest_cherrypy"]["port"]]
        elif "rest_tornado" in self.config:
            self.check_ports = [self.config["rest_tornado"]["port"]]
        else:
            msg = (
                "The salt-master configuration for this salt-api instance does not seem to have any "
                "api properly configured."
            )
            raise pytest.UsageError(msg)
        super().__attrs_post_init__()

    @classmethod
    def _configure(
        cls,
        factories_manager,  # noqa: ARG003
        daemon_id,  # noqa: ARG003
        root_dir=None,  # noqa: ARG003
        defaults=None,  # noqa: ARG003
        overrides=None,  # noqa: ARG003
    ):
        msg = "The salt-api daemon is not configurable. It uses the salt-master config that it's attached to."
        raise pytest.UsageError(msg)

    @classmethod
    def _get_verify_config_entries(cls, config):  # noqa: ARG003
        return []

    @classmethod
    def load_config(cls, config_file, config):  # noqa: ARG003
        """
        Return the loaded configuration.
        """
        msg = (
            "The salt-api daemon does not have it's own config file. It uses the salt-master config that "
            "it's attached to."
        )
        raise pytest.UsageError(msg)

    def get_check_events(self):
        """
        Return salt events to check.

        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        return []
