"""
PyTest Salt Factories related exceptions.
"""
import sys

if sys.version_info >= (3, 7):

    def __getattr__(name):
        if name in ("FactoryTimeout", "FactoryNotStarted"):
            import pytestshellutils.exceptions
            from saltfactories.utils import warn_until

            warn_until(
                "2.0.0",
                "The '{}' exception is now in 'pytestshellutils.exceptions' and importing it "
                "from 'saltfactories.exceptions' is deprecated and will cease to work after "
                "pytest-salt-factories {{version}}.".format(name),
            )
            return getattr(pytestshellutils.exceptions, name)
        else:
            raise AttributeError("module '{}' has no '{}' attribute".format(__name__, name))

else:
    from pytestshellutils.exceptions import (  # noqa: F401  pylint: disable=unused-import
        FactoryNotStarted,
    )
    from pytestshellutils.exceptions import (  # noqa: F401  pylint: disable=unused-import
        FactoryTimeout,
    )


class SaltFactoriesException(Exception):
    """
    Base exception for all pytest salt factories.
    """
