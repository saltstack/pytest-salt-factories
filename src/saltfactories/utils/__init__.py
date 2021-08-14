"""
..
    PYTEST_DONT_REWRITE

Utility functions
"""
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
    return salt.utils.user.get_user()


def format_callback_to_string(callback, args=None, kwargs=None):
    """
    Convert a callback, its arguments and keyword arguments to a string suitable for logging purposes

    :param ~collections.abc.Callable,str callback:
        The callback function
    :param list,tuple args:
        The callback arguments
    :param dict kwargs:
        The callback keyword arguments
    :rtype: str
    """
    if not isinstance(callback, str):
        try:
            callback_str = "{}(".format(callback.__qualname__)
        except AttributeError:
            callback_str = "{}(".format(callback.__name__)
    else:
        callback_str = "{}(".format(callback)
    if args:
        callback_str += ", ".join([repr(arg) for arg in args])
    if kwargs:
        callback_str += ", ".join(["{}={!r}".format(k, v) for (k, v) in kwargs.items()])
    callback_str += ")"
    return callback_str
