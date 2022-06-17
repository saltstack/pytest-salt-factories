# pylint: disable=wildcard-import,unused-wildcard-import
from pytestshellutils.utils.processes import *

from saltfactories.utils import warn_until

warn_until(
    "3.0.0",
    "The 'processes' module is deprecated and will cease to exist after "
    "pytest-salt-factories {version}. Please import 'processes' from "
    "'pytestshellutils.utils' instead.",
)
