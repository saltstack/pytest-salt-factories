# -*- coding: utf-8 -*-
'''
tests.unit.utils.processes.test_shellresult
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test saltfactories.utils.processes.ShellResult
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import 3rd-party libs
import pytest

# Import Salt Factories libs
from saltfactories.utils.processes import ShellResult


@pytest.mark.parametrize('exitcode', [None, 1.0, -1.0, '0'])
def test_non_int_exitcode_raises_exception(exitcode):
    with pytest.raises(ValueError):
        ShellResult(exitcode, None, None, None)
