"""
tests.unit.utils.processes.test_shellresult
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test saltfactories.utils.processes.ShellResult
"""
import pprint
import textwrap

import pytest

from saltfactories.utils.processes import ShellResult


@pytest.mark.parametrize("exitcode", [None, 1.0, -1.0, "0"])
def test_non_int_exitcode_raises_exception(exitcode):
    with pytest.raises(ValueError):
        ShellResult(exitcode, None, None)


def test_attributes():
    exitcode = 0
    stdout = "STDOUT"
    stderr = "STDERR"
    json = None
    cmdline = None
    ret = ShellResult(exitcode, stdout, stderr)
    assert ret.exitcode == exitcode
    assert ret.stdout == stdout
    assert ret.stderr == stderr
    assert ret.json == json
    assert ret.cmdline == cmdline
    json = {1: 1}
    ret = ShellResult(exitcode, stdout, stderr, json=json)
    assert ret.exitcode == exitcode
    assert ret.stdout == stdout
    assert ret.stderr == stderr
    assert ret.json == json
    assert ret.cmdline == cmdline
    cmdline = [1, 2, 3]
    ret = ShellResult(exitcode, stdout, stderr, json=json, cmdline=cmdline)
    assert ret.exitcode == exitcode
    assert ret.stdout == stdout
    assert ret.stderr == stderr
    assert ret.json == json
    assert ret.cmdline == cmdline


def test_str_formatting():
    exitcode = 0
    stdout = "STDOUT"
    stderr = "STDERR"
    json = None
    cmdline = None
    ret = ShellResult(exitcode, stdout, stderr)
    expected = textwrap.dedent(
        """\
        ShellResult
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
    json = {1: 1}
    ret = ShellResult(exitcode, stdout, stderr, json=json)
    expected = textwrap.dedent(
        """\
        ShellResult
         Exitcode: {}
         Process Output:
           >>>>> STDOUT >>>>>
        {}
           <<<<< STDOUT <<<<<
           >>>>> STDERR >>>>>
        {}
           <<<<< STDERR <<<<<
         JSON Object:
        {}
    """.format(
            exitcode, stdout, stderr, "".join("  {}".format(line) for line in pprint.pformat(json))
        )
    )
    assert str(ret) == expected
    cmdline = [1, 2, 3]
    ret = ShellResult(exitcode, stdout, stderr, json=json, cmdline=cmdline)
    expected = textwrap.dedent(
        """\
        ShellResult
         Command Line: {!r}
         Exitcode: {}
         Process Output:
           >>>>> STDOUT >>>>>
        {}
           <<<<< STDOUT <<<<<
           >>>>> STDERR >>>>>
        {}
           <<<<< STDERR <<<<<
         JSON Object:
        {}
    """.format(
            cmdline,
            exitcode,
            stdout,
            stderr,
            "".join("  {}".format(line) for line in pprint.pformat(json)),
        )
    )
    assert str(ret) == expected
