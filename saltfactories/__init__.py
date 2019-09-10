# -*- coding: utf-8 -*-
'''
NG PyTest Salt Plugin
'''
# pragma: no cover

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import re

# Import Salt Factories libs
from saltfactories._version import get_versions

# Store the version attribute
__version__ = get_versions()['version']
del get_versions

# Define __version_info__ attribute
VERSION_INFO_REGEX = re.compile(
    r'(?P<year>[\d]{4})\.(?P<month>[\d]{1,2})\.(?P<day>[\d]{1,2})'
    r'(?:\.dev0\+(?P<commits>[\d]+)\.(?:.*))?'
)
try:
    __version_info__ = tuple([int(p) for p in VERSION_INFO_REGEX.match(__version__).groups() if p])
except AttributeError:
    __version_info__ = (-1, -1, -1)
finally:
    del VERSION_INFO_REGEX
