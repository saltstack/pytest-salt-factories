"""
saltfactories.utils
~~~~~~~~~~~~~~~~~~~

Utility functions
"""
import os
import random
import string
import sys
from functools import lru_cache

try:
    import salt.utils.user
except ImportError:  # pragma: no cover
    # We need salt to test salt with saltfactories, and, when pytest is rewriting modules for proper assertion
    # reporting, we still haven't had a chance to inject the salt path into sys.modules, so we'll hit this
    # import error, but its safe to pass
    pass


def random_string(prefix, size=6, uppercase=True, lowercase=True, digits=True):
    """
    Generates a random string.

    Args:
        prefix(str): The prefix for the random string
        size(int): The size of the random string
        uppercase(bool): If true, include uppercased ascii chars in choice sample
        lowercase(bool): If true, include lowercased ascii chars in choice sample
        digits(bool): If true, include digits in choice sample
    Returns:
        str: The random string
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
