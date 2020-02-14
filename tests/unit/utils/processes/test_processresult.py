# -*- coding: utf-8 -*-
"""
tests.unit.utils.processes.test_processresult
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test saltfactories.utils.processes.ProcessResult
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import pytest

from saltfactories.utils.processes import ProcessResult


@pytest.mark.parametrize("exitcode", [None, 1.0, -1.0, "0"])
def test_non_int_exitcode_raises_exception(exitcode):
    with pytest.raises(ValueError):
        ProcessResult(exitcode, None, None)
