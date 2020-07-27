"""
saltfactories.utils.processes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Process related utilities
"""
import pprint
import subprocess
import tempfile
import weakref

import attr

from saltfactories.exceptions import FactoryTimeout
from saltfactories.utils.processes.helpers import terminate_process


class Popen(subprocess.Popen):
    def __init__(self, *args, **kwargs):
        for key in ("stdout", "stderr"):
            if key in kwargs:
                raise RuntimeError(
                    "{}.Popen() does not accept {} as a valid keyword argument".format(
                        __name__, key
                    )
                )
        stdout = tempfile.SpooledTemporaryFile(512000)
        kwargs["stdout"] = stdout
        stderr = tempfile.SpooledTemporaryFile(512000)
        kwargs["stderr"] = stderr
        super().__init__(*args, **kwargs)
        self.__stdout = stdout
        self.__stderr = stderr
        weakref.finalize(self, stdout.close)
        weakref.finalize(self, stderr.close)

    def communicate(self, input=None):  # pylint: disable=arguments-differ
        super().communicate(input)
        stdout = stderr = None
        if self.__stdout:
            self.__stdout.flush()
            self.__stdout.seek(0)
            stdout = self.__stdout.read()

            # We want str type on Py3 and Unicode type on Py2
            # pylint: disable=undefined-variable
            stdout = stdout.decode(__salt_system_encoding__)
            # pylint: enable=undefined-variable
        if self.__stderr:
            self.__stderr.flush()
            self.__stderr.seek(0)
            stderr = self.__stderr.read()

            # We want str type on Py3 and Unicode type on Py2
            # pylint: disable=undefined-variable
            stderr = stderr.decode(__salt_system_encoding__)
            # pylint: enable=undefined-variable
        return stdout, stderr


@attr.s(frozen=True)
class ProcessResult:
    """
    This class serves the purpose of having a common result class which will hold the
    resulting data from a subprocess command.
    """

    exitcode = attr.ib()
    stdout = attr.ib()
    stderr = attr.ib()
    cmdline = attr.ib(default=None, kw_only=True)

    @exitcode.validator
    def _validate_exitcode(self, attribute, value):
        if not isinstance(value, int):
            raise ValueError("'exitcode' needs to be an integer, not '{}'".format(type(value)))

    def __str__(self):
        message = self.__class__.__name__
        if self.cmdline:
            message += "\n Command Line: {}".format(self.cmdline)
        if self.exitcode is not None:
            message += "\n Exitcode: {}".format(self.exitcode)
        if self.stdout or self.stderr:
            message += "\n Process Output:"
        if self.stdout:
            message += "\n   >>>>> STDOUT >>>>>\n{}\n   <<<<< STDOUT <<<<<".format(self.stdout)
        if self.stderr:
            message += "\n   >>>>> STDERR >>>>>\n{}\n   <<<<< STDERR <<<<<".format(self.stderr)
        return message + "\n"


@attr.s(frozen=True)
class ShellResult(ProcessResult):
    """
    This class serves the purpose of having a common result class which will hold the
    resulting data from a subprocess command.
    """

    json = attr.ib(default=None, kw_only=True)

    def __str__(self):
        message = super().__str__().rstrip()
        if self.json:
            message += "\n JSON Object:\n"
            message += "".join("  {}".format(line) for line in pprint.pformat(self.json))
        return message + "\n"

    def __eq__(self, other):
        """
        Allow comparison against the parsed JSON or the output
        """
        if self.json:
            return self.json == other
        return self.stdout == other
