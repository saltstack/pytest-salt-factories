# -*- coding: utf-8 -*-
"""
saltfactories.utils.compat
~~~~~~~~~~~~~~~~~~~~~~~~~~

Imports compatability layer
"""
import sys
import weakref

# pragma: no cover
# pylint: disable=unused-import,invalid-name
try:
    from unittest import mock
except ImportError:
    import mock

if sys.version_info < (3,):
    import backports.weakref

    weakref.finalize = backports.weakref.finalize
# pylint: enable=unused-import,invalid-name


def has_unittest_attr(item, attr):
    """
    Check if a test item has a specific attribute set.

    This is basically a compatability layer while Salt migrates to PyTest
    """
    if hasattr(item.obj, attr):
        return True
    if item.cls and hasattr(item.cls, attr):
        return True
    if item.parent and hasattr(item.parent.obj, attr):
        return True
    return False
