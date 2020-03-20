# -*- coding: utf-8 -*-
"""
tests.unit.utils.processes.bases.test_processresult
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test saltfactories.utils.processes.bases.ProcessResult
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import pytest

from saltfactories.utils.processes.bases import ProcessResult


@pytest.mark.parametrize("exitcode", [None, 1.0, -1.0, "0"])
def test_non_int_exitcode_raises_exception(exitcode):
    with pytest.raises(ValueError):
        ProcessResult(exitcode, None, None)


def test_attributes():
    exitcode = 0
    stdout = "STDOUT"
    stderr = "STDERR"
    cmdline = None
    ret = ProcessResult(exitcode, stdout, stderr)
    assert ret.exitcode == exitcode
    assert ret.stdout == stdout
    assert ret.stderr == stderr
    assert ret.cmdline == cmdline
    cmdline = [1, 2, 3]
    ret = ProcessResult(exitcode, stdout, stderr, cmdline)
    assert ret.exitcode == exitcode
    assert ret.stdout == stdout
    assert ret.stderr == stderr
    assert ret.cmdline == cmdline
