"""
This module's sole purpose is to have the standard library time module functions under a different
namespace to be used in salt-factories so that projects using salt-factories which need to mock time
functions don't influence salt-factories run time behavior.
"""
from time import *  # pylint: disable=wildcard-import,unused-wildcard-import
