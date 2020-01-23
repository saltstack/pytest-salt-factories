# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.version


def pytest_report_header():
    return 'salt-version: {}'.format(salt.version.__version__)
