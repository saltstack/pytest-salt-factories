# -*- coding: utf-8 -*-
'''
pytestsalt.utils.compat
~~~~~~~~~~~~~~~~~~~~~~~

Imports compatability layer
'''
# pylint: disable=unused-import

try:
    # Salt > 2017.1.1
    # pylint: disable=invalid-name
    import salt.utils.files

    fopen = salt.utils.files.fopen
except AttributeError:
    # Salt <= 2017.1.1
    # pylint: disable=invalid-name
    fopen = salt.utils.fopen

try:
    # Salt >= 2018.3.0
    # pylint: disable=invalid-name
    from salt.utils.path import which
except ImportError:
    # Salt < 2018.3.0
    # pylint: disable=invalid-name
    from salt.utils import which
