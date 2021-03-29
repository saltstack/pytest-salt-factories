"""
saltfactories.utils.socket
==========================

This module's sole purpose is to have the standard library :py:mod:`socket` module functions under a different
namespace to be used in salt-factories so that projects using it, which need to mock :py:mod:`socket` functions,
don't influence the salt-factories run time behavior.
"""
from socket import *  # pylint: disable=wildcard-import,unused-wildcard-import
