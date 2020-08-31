"""
tests.unit.utils.processes.test_processresult
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test saltfactories.utils.processes.ProcessResult
"""
import textwrap

import pytest

from saltfactories.utils.processes import ProcessResult


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
    ret = ProcessResult(exitcode, stdout, stderr, cmdline=cmdline)
    assert ret.exitcode == exitcode
    assert ret.stdout == stdout
    assert ret.stderr == stderr
    assert ret.cmdline == cmdline


def test_str_formatting():
    exitcode = 0
    stdout = "STDOUT"
    stderr = "STDERR"
    cmdline = None
    ret = ProcessResult(exitcode, stdout, stderr)
    expected = textwrap.dedent(
        """\
        ProcessResult
         Exitcode: {}
         Process Output:
           >>>>> STDOUT >>>>>
        {}
           <<<<< STDOUT <<<<<
           >>>>> STDERR >>>>>
        {}
           <<<<< STDERR <<<<<
    """.format(
            exitcode, stdout, stderr
        )
    )
    assert str(ret) == expected
    cmdline = [1, 2, 3]
    ret = ProcessResult(exitcode, stdout, stderr, cmdline=cmdline)
    expected = textwrap.dedent(
        """\
        ProcessResult
         Command Line: {!r}
         Exitcode: {}
         Process Output:
           >>>>> STDOUT >>>>>
        {}
           <<<<< STDOUT <<<<<
           >>>>> STDERR >>>>>
        {}
           <<<<< STDERR <<<<<
    """.format(
            cmdline,
            exitcode,
            stdout,
            stderr,
        )
    )
    assert str(ret) == expected
