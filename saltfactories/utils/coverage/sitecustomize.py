# -*- coding: utf-8 -*-
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

try:
    import coverage

    coverage.process_startup()
except ImportError:
    pass
