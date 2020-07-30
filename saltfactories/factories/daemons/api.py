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
        super().__attrs_post_init__()
        if "rest_cherrypy" in self.config:
            self.check_ports = [self.config["rest_cherrypy"]["port"]]
        elif "rest_tornado" in self.config:
            self.check_ports = [self.config["rest_tornado"]["port"]]
        else:
            raise RuntimeError(
                "The salt-master configuration for this salt-api instance does not seem to have "
                "any api properly configured."
            )

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        return []
