"""
Utility functions.

..
    PYTEST_DONT_REWRITE
"""
import inspect
import pathlib
import random
import string
import sys
import warnings
from functools import lru_cache
from typing import Optional
from typing import Type

import packaging.version
import salt.utils.user

import saltfactories


def random_string(prefix, size=6, uppercase=True, lowercase=True, digits=True):
    """
    Generates a random string.

    :keyword str prefix: The prefix for the random string
    :keyword int size: The size of the random string
    :keyword bool uppercase: If true, include upper-cased ascii chars in choice sample
    :keyword bool lowercase: If true, include lower-cased ascii chars in choice sample
    :keyword bool digits: If true, include digits in choice sample
    :return str: The random string
    """
    if not any([uppercase, lowercase, digits]):
        raise RuntimeError("At least one of 'uppercase', 'lowercase' or 'digits' needs to be true")
    choices = []
    if uppercase:
        choices.extend(string.ascii_uppercase)
    if lowercase:
        choices.extend(string.ascii_lowercase)
    if digits:
        choices.extend(string.digits)

    return prefix + "".join(random.choice(choices) for _ in range(size))


@lru_cache(maxsize=1)
def running_username():
    """
    Return the username that is running the code.
    """
    return salt.utils.user.get_user()


def cast_to_pathlib_path(value):
    """
    Cast the passed value to an instance of ``pathlib.Path``.
    """
    if isinstance(value, pathlib.Path):
        return value
    try:
        return pathlib.Path(value.strpath)
    except AttributeError:
        return pathlib.Path(str(value))


def warn_until(
    version: str,
    message: str,
    category: Type[Warning] = DeprecationWarning,
    stacklevel: Optional[int] = None,
    _dont_call_warnings: bool = False,
    _pkg_version_: Optional[str] = None,
) -> None:
    """
    Show a deprecation warning.

    Helper function to raise a warning, by default, a ``DeprecationWarning``,
    until the provided ``version``, after which, a ``RuntimeError`` will
    be raised to remind the developers to remove the warning because the
    target version has been reached.

    :param version:
        The version string after which the warning becomes a ``RuntimeError``.
        For example ``2.1``.
    :param message:
        The warning message to be displayed.
    :param category:
        The warning class to be thrown, by default ``DeprecationWarning``
    :param stacklevel:
        There should be no need to set the value of ``stacklevel``.
    :param _dont_call_warnings:
        This parameter is used just to get the functionality until the actual
        error is to be issued. When we're only after the version checks to
        raise a ``RuntimeError``.
    """
    _version = packaging.version.parse(version)
    if _pkg_version_ is None:
        _pkg_version_ = saltfactories.__version__  # type: ignore[attr-defined]
    _pkg_version = packaging.version.parse(_pkg_version_)

    if stacklevel is None:
        # Attribute the warning to the calling function, not to warn_until()
        stacklevel = 3

    if _pkg_version >= _version:
        caller = inspect.getframeinfo(sys._getframe(stacklevel - 1))
        raise RuntimeError(
            "The warning triggered on filename '{filename}', line number "
            "{lineno}, is supposed to be shown until version "
            "{until_version} is released. Current version is now "
            "{version}. Please remove the warning.".format(
                filename=caller.filename,
                lineno=caller.lineno,
                until_version=_pkg_version_,
                version=version,
            ),
        )

    if _dont_call_warnings is False:
        warnings.warn(
            message.format(version=version),
            category,
            stacklevel=stacklevel,
        )
