# pylint: disable=wildcard-import,unused-wildcard-import
from pytestshellutils.utils.ports import *

from saltfactories.utils import warn_until

warn_until(
    "3.0.0",
    "The 'ports' module is deprecated and will cease to exist after "
    "pytest-salt-factories {version}. Please import 'ports' from "
    "'pytestshellutils.utils' instead.",
)
