"""
saltfactories.utils.time
========================

This module's sole purpose is to have the standard library :py:mod:`time` module functions under a different
namespace to be used in salt-factories so that projects using it, which need to mock :py:mod:`time` functions,
don't influence the salt-factories run time behavior.
"""
from time import *  # pylint: disable=wildcard-import,unused-wildcard-import
