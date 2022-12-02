"""
PyTest Salt Factories related exceptions.
"""


def __getattr__(name):
    if name in ("FactoryTimeout", "FactoryNotStarted"):
        import pytestshellutils.exceptions  # pylint: disable=import-outside-toplevel
        from saltfactories.utils import warn_until  # pylint: disable=import-outside-toplevel

        warn_until(
            "3.0.0",
            "The '{}' exception is now in 'pytestshellutils.exceptions' and importing it "
            "from 'saltfactories.exceptions' is deprecated and will cease to work after "
            "pytest-salt-factories {{version}}.".format(name),
        )
        return getattr(pytestshellutils.exceptions, name)
    else:
        raise AttributeError("module '{}' has no '{}' attribute".format(__name__, name))
