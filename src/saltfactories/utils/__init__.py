"""
Utility functions.

..
    PYTEST_DONT_REWRITE
"""
import pathlib
import random
import string
from functools import lru_cache

import salt.utils.user


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
