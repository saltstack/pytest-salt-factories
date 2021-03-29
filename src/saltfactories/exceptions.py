"""
PyTest Salt Factories related exceptions
"""
import traceback


class SaltFactoriesException(Exception):
    """
    Base exception for all pytest salt factories
    """


class ProcessFailed(SaltFactoriesException):
    """
    Exception raised when a sub-process fails

    :param str message:
        The exception message
    :keyword list,tuple cmdline:
        The command line used to start the process
    :keyword str stdout:
        The ``stdout`` returned by the process
    :keyword str stderr:
        The ``stderr`` returned by the process
    :keyword int exitcode:
        The exitcode returned by the process
    :keyword Exception exc:
        The original exception raised
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


class FactoryFailure(ProcessFailed):
    """
    Exception raised when a sub-process fails on one of the factories
    """


class FactoryNotStarted(FactoryFailure):
    """
    Exception raised when a factory failed to start

    Please look at :py:class:`~saltfactories.exceptions.FactoryFailure` for the supported keyword
    arguments documentation.
    """


class FactoryNotRunning(FactoryFailure):
    """
    Exception raised when trying to use a factory's `.stopped` context manager and the factory is not running

    Please look at :py:class:`~saltfactories.exceptions.FactoryFailure` for the supported keyword
    arguments documentation.
    """


class ProcessNotStarted(FactoryFailure):
    """
    Exception raised when a process failed to start

    Please look at :py:class:`~saltfactories.exceptions.FactoryFailure` for the supported keyword
    arguments documentation.
    """


class FactoryTimeout(FactoryNotStarted):
    """
    Exception raised when a process timed-out

    Please look at :py:class:`~saltfactories.exceptions.FactoryFailure` for the supported keyword
    arguments documentation.
    """
