"""
    tests.unit.utils.test_random_string
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Unit tests for the random string generator
"""
import pytest

from saltfactories.utils import random_string


def test_raises_runtimeerror_on_bad_arguments():
    with pytest.raises(RuntimeError):
        random_string("foo", uppercase=False, lowercase=False, digits=False)
