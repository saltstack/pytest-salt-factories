"""
    tests.unit.test_exceptions
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Exceptions unit tests
"""
import textwrap
import traceback

import pytest

import saltfactories.exceptions


def test_process_failed_message():
    message = "The message"
    with pytest.raises(saltfactories.exceptions.FactoryFailure) as exc:
        raise saltfactories.exceptions.FactoryFailure(message)
    assert str(exc.value) == message


def test_process_failed_cmdline():
    message = "The message"
    cmdline = ["python", "--version"]
    expected = textwrap.dedent(
        """\
        {}
         Command Line: {!r}
    """.format(
            message, cmdline
        )
    )
    with pytest.raises(saltfactories.exceptions.FactoryFailure) as exc:
        raise saltfactories.exceptions.FactoryFailure(message, cmdline=cmdline)
    output = str(exc.value)
    assert output == expected


def test_process_failed_exitcode():
    message = "The message"
    exitcode = 1
    expected = textwrap.dedent(
        """\
        {}
         Exitcode: {}
    """.format(
            message, exitcode
        )
    )
    with pytest.raises(saltfactories.exceptions.FactoryFailure) as exc:
        raise saltfactories.exceptions.FactoryFailure(message, exitcode=exitcode)
    output = str(exc.value)
    assert output == expected


def test_process_failed_stdout():
    message = "The message"
    stdout = "This is the STDOUT"
    expected = textwrap.dedent(
        """\
        {}
         Process Output:
           >>>>> STDOUT >>>>>
        {}
           <<<<< STDOUT <<<<<
    """.format(
            message, stdout
        )
    )
    with pytest.raises(saltfactories.exceptions.FactoryFailure) as exc:
        raise saltfactories.exceptions.FactoryFailure(message, stdout=stdout)
    output = str(exc.value)
    assert output == expected


def test_process_failed_stderr():
    message = "The message"
    stderr = "This is the STDERR"
    expected = textwrap.dedent(
        """\
        {}
         Process Output:
           >>>>> STDERR >>>>>
        {}
           <<<<< STDERR <<<<<
    """.format(
            message, stderr
        )
    )
    with pytest.raises(saltfactories.exceptions.FactoryFailure) as exc:
        raise saltfactories.exceptions.FactoryFailure(message, stderr=stderr)
    output = str(exc.value)
    assert output == expected


def test_process_failed_stdout_and_stderr():
    message = "The message"
    stdout = "This is the STDOUT"
    stderr = "This is the STDERR"
    expected = textwrap.dedent(
        """\
        {}
         Process Output:
           >>>>> STDOUT >>>>>
        {}
           <<<<< STDOUT <<<<<
           >>>>> STDERR >>>>>
        {}
           <<<<< STDERR <<<<<
    """.format(
            message, stdout, stderr
        )
    )
    with pytest.raises(saltfactories.exceptions.FactoryFailure) as exc:
        raise saltfactories.exceptions.FactoryFailure(message, stdout=stdout, stderr=stderr)
    output = str(exc.value)
    assert output == expected


def test_process_failed_cmdline_stdout_and_stderr():
    message = "The message"
    stdout = "This is the STDOUT"
    stderr = "This is the STDERR"
    cmdline = ["python", "--version"]
    expected = textwrap.dedent(
        """\
        {}
         Command Line: {!r}
         Process Output:
           >>>>> STDOUT >>>>>
        {}
           <<<<< STDOUT <<<<<
           >>>>> STDERR >>>>>
        {}
           <<<<< STDERR <<<<<
    """.format(
            message, cmdline, stdout, stderr
        )
    )
    with pytest.raises(saltfactories.exceptions.FactoryFailure) as exc:
        raise saltfactories.exceptions.FactoryFailure(
            message, cmdline=cmdline, stdout=stdout, stderr=stderr
        )
    output = str(exc.value)
    assert output == expected


def test_process_failed_cmdline_stdout_stderr_and_exitcode():
    message = "The message"
    stdout = "This is the STDOUT"
    stderr = "This is the STDERR"
    cmdline = ["python", "--version"]
    exitcode = 1
    expected = textwrap.dedent(
        """\
        {}
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
            message, cmdline, exitcode, stdout, stderr
        )
    )
    with pytest.raises(saltfactories.exceptions.FactoryFailure) as exc:
        raise saltfactories.exceptions.FactoryFailure(
            message, cmdline=cmdline, stdout=stdout, stderr=stderr, exitcode=exitcode
        )
    output = str(exc.value)
    assert output == expected


def test_process_failed_exc():
    with pytest.raises(ZeroDivisionError) as exc:
        1 / 0  # pylint: disable=pointless-statement
    excinfo = exc._excinfo
    formatted_exception = "".join(traceback.format_exception(*excinfo)).rstrip()
    message = "The message"
    expected = "{}\n{}\n".format(message, formatted_exception)
    with pytest.raises(saltfactories.exceptions.FactoryFailure) as exc:
        raise saltfactories.exceptions.FactoryFailure(message, exc=excinfo)
    output = str(exc.value)
    assert output == expected


def test_process_failed_cmdline_stdout_stderr_and_exc():
    with pytest.raises(ZeroDivisionError) as exc:
        1 / 0  # pylint: disable=pointless-statement
    excinfo = exc._excinfo
    formatted_exception = "".join(traceback.format_exception(*excinfo)).rstrip()
    message = "The message"
    stdout = "This is the STDOUT"
    stderr = "This is the STDERR"
    cmdline = ["python", "--version"]
    expected = textwrap.dedent(
        """\
        {}
         Command Line: {!r}
         Process Output:
           >>>>> STDOUT >>>>>
        {}
           <<<<< STDOUT <<<<<
           >>>>> STDERR >>>>>
        {}
           <<<<< STDERR <<<<<
    """.format(
            message, cmdline, stdout, stderr
        )
    )
    expected += formatted_exception + "\n"
    with pytest.raises(saltfactories.exceptions.FactoryFailure) as exc:
        raise saltfactories.exceptions.FactoryFailure(
            message, cmdline=cmdline, stdout=stdout, stderr=stderr, exc=excinfo
        )
    output = str(exc.value)
    assert output == expected
