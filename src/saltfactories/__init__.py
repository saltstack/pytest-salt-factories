import pathlib
import re
import sys

try:
    from .version import __version__
except ImportError:  # pragma: no cover
    __version__ = "0.0.0.not-installed"
    try:
        from importlib.metadata import version, PackageNotFoundError

        try:
            __version__ = version("pytest-salt-factories")
        except PackageNotFoundError:
            # package is not installed
            pass
    except ImportError:
        try:
            from importlib_metadata import version, PackageNotFoundError

            try:
                __version__ = version("pytest-salt-factories")
            except PackageNotFoundError:
                # package is not installed
                pass
        except ImportError:
            try:
                from pkg_resources import get_distribution, DistributionNotFound

                try:
                    __version__ = get_distribution("pytest-salt-factories").version
                except DistributionNotFound:
                    # package is not installed
                    pass
            except ImportError:
                # pkg resources isn't even available?!
                pass


# Define __version_info__ attribute
VERSION_INFO_REGEX = re.compile(
    r"(?P<major>[\d]+)\.(?P<minor>[\d]+)\.(?P<patch>[\d]+)"
    r"(?:\.dev(?P<commits>[\d]+)\+g(?P<sha>[a-z0-9]+)\.d(?P<date>[\d]+))?"
)
try:
    __version_info__ = tuple(
        int(p) if p.isdigit() else p for p in VERSION_INFO_REGEX.match(__version__).groups() if p
    )
except AttributeError:  # pragma: no cover
    __version_info__ = (-1, -1, -1)
finally:
    del VERSION_INFO_REGEX


# Define some constants
CODE_ROOT_DIR = pathlib.Path(__file__).resolve().parent
IS_WINDOWS = sys.platform.startswith("win")
IS_DARWIN = IS_OSX = sys.platform.startswith("darwin")
