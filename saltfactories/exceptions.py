"""
saltfactories.exceptions
~~~~~~~~~~~~~~~~~~~~~~~~

PyTest Salt Factories related exceptions
"""
import traceback


class SaltFactoriesException(Exception):
    """
    Base exception for all pytest salt factories
    """


class FactoryFailure(SaltFactoriesException):
    """
    Exception raised when a sub-process fails
    """

    def __init__(self, message, cmdline=None, stdout=None, stderr=None, exitcode=None, exc=None):
        super().__init__()
        self.message = message
        self.cmdline = cmdline
        self.stdout = stdout
        self.stderr = stderr
        self.exitcode = exitcode
        self.exc = exc

    def __str__(self):
        message = self.message
        append_new_line = False
        if self.cmdline:
            message += "\n Command Line: {}".format(self.cmdline)
            append_new_line = True
        if self.exitcode is not None:
            append_new_line = True
            message += "\n Exitcode: {}".format(self.exitcode)
        if self.stdout or self.stderr:
            append_new_line = True
            message += "\n Process Output:"
        if self.stdout:
            message += "\n   >>>>> STDOUT >>>>>\n{}\n   <<<<< STDOUT <<<<<".format(self.stdout)
        if self.stderr:
            message += "\n   >>>>> STDERR >>>>>\n{}\n   <<<<< STDERR <<<<<".format(self.stderr)
        if self.exc:
            append_new_line = True
            message += "\n{}".format("".join(traceback.format_exception(*self.exc)).rstrip())
        if append_new_line:
            message += "\n"
        return message


class FactoryNotStarted(FactoryFailure):
    """
    Exception raised when a factory failed to start
    """


class FactoryNotRunning(FactoryFailure):
    """
    Exception raised when trying to use a factory's `.stopped` context manager and the factory is not running
    """


class ProcessNotStarted(FactoryFailure):
    """
    Exception raised when a process failed to start
    """


class FactoryTimeout(FactoryNotStarted):
    """
    Exception raised when a process timed-out
    """
