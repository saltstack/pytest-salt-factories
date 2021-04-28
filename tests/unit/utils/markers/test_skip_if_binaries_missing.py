"""
    tests.unit.utils.markers.test_skip_if_binaries_missing
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the "skip_if_binaries_missing" marker helper
"""
import os
import sys

import pytest

import saltfactories.utils.markers as markers


@pytest.fixture
def python_binary():
    return os.path.basename(sys.executable)


def test_single_existing(python_binary):
    assert markers.skip_if_binaries_missing([python_binary]) is None


def test_multiple_existing(python_binary):
    assert markers.skip_if_binaries_missing([python_binary, "pip"]) is None


def test_single_non_existing_with_message():
    reason = markers.skip_if_binaries_missing(["python9"], reason="Dam!")
    assert reason is not None
    assert reason == "Dam!"


def test_multiple_one_missing(python_binary):
    reason = markers.skip_if_binaries_missing([python_binary, "pip9"])
    assert reason is not None
    assert reason == "The 'pip9' binary was not found"


def test_multiple_all_missing():
    reason = markers.skip_if_binaries_missing(["python9", "pip9"])
    assert reason is not None
    assert reason == "The 'python9' binary was not found"


def test_multiple_one_missing_check_all_false(python_binary):
    reason = markers.skip_if_binaries_missing([python_binary, "pip9"], check_all=False)
    # We should get no message back because the python binary is found
    assert reason is None, reason
    reason = markers.skip_if_binaries_missing(["python9", "pip"], check_all=False)
    # We should get no message back because the pip binary is found
    assert reason is None, reason


def test_multiple_one_missing_check_all_false_with_message(python_binary):
    reason = markers.skip_if_binaries_missing(
        [python_binary, "pip9"], reason="Dam!", check_all=False
    )
    # We should get no message back because the python binary is found
    assert reason is None


def test_multiple_missing_check_all_false():
    reason = markers.skip_if_binaries_missing(["python9", "pip9"], check_all=False)
    assert reason is not None
    assert reason == "None of the following binaries was found: python9, pip9"


def test_multiple_missing_check_all_false_with_message():
    reason = markers.skip_if_binaries_missing(["python9", "pip9"], reason="Dam!", check_all=False)
    assert reason is not None
    assert reason == "Dam!"
