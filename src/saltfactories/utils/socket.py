"""
This module's sole purpose is to have the standard library socket module functions under a different
namespace to be used in salt-factories so that projects using salt-factories which need to mock socket
functions don't influence salt-factories run time behavior.
"""
from socket import *  # pylint: disable=wildcard-import,unused-wildcard-import
