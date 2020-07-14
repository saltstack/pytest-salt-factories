"""
    tests.unit.utils.markers.test_skip_if_not_root
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the "skip_if_not_root" marker helper
"""
import sys
from unittest import mock

import saltfactories.utils.markers


def test_when_root():
    if sys.platform.startswith("win"):
        with mock.patch("salt.utils.win_functions.is_admin", return_value=True):
            assert saltfactories.utils.markers.skip_if_not_root() is None
    else:
        with mock.patch("os.getuid", return_value=0):
            assert saltfactories.utils.markers.skip_if_not_root() is None


def test_when_not_root():
    if sys.platform.startswith("win"):
        with mock.patch("salt.utils.win_functions.is_admin", return_value=False):
            assert saltfactories.utils.markers.skip_if_not_root() is not None
    else:
        with mock.patch("os.getuid", return_value=1):
            assert saltfactories.utils.markers.skip_if_not_root() is not None
