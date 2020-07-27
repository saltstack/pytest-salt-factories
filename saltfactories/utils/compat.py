"""
saltfactories.utils.compat
~~~~~~~~~~~~~~~~~~~~~~~~~~

Compatibility layer
"""


def has_unittest_attr(item, attr):
    """
    Check if a test item has a specific attribute set.

    This is basically a compatibility layer while Salt migrates to PyTest
    """
    if hasattr(item.obj, attr):
        return True
    if item.cls and hasattr(item.cls, attr):
        return True
    if item.parent and hasattr(item.parent.obj, attr):
        return True
    return False
