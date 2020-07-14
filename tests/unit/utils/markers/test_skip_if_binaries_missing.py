"""
    tests.unit.utils.markers.test_skip_if_binaries_missing
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the "skip_if_binaries_missing" marker helper
"""
import saltfactories.utils.markers as markers


def test_single_existing():
    assert markers.skip_if_binaries_missing(["python"]) is None


def test_multiple_existing():
    assert markers.skip_if_binaries_missing(["python", "pip"]) is None


def test_single_non_existing_with_message():
    reason = markers.skip_if_binaries_missing(["python9"], message="Dam!")
    assert reason is not None
    assert reason == "Dam! The 'python9' binary was not found"


def test_multiple_one_missing():
    reason = markers.skip_if_binaries_missing(["python", "pip9"])
    assert reason is not None
    assert reason == "The 'pip9' binary was not found"


def test_multiple_all_missing():
    reason = markers.skip_if_binaries_missing(["python9", "pip9"])
    assert reason is not None
    assert reason == "The 'python9' binary was not found"


def test_multiple_one_missing_check_all_false():
    reason = markers.skip_if_binaries_missing(["python", "pip9"], check_all=False)
    # We should get no message back because the python binary is found
    assert reason is None, reason
    reason = markers.skip_if_binaries_missing(["python9", "pip"], check_all=False)
    # We should get no message back because the pip binary is found
    assert reason is None, reason


def test_multiple_one_missing_check_all_false_with_message():
    reason = markers.skip_if_binaries_missing(["python", "pip9"], message="Dam!", check_all=False)
    # We should get no message back because the python binary is found
    assert reason is None


def test_multiple_missing_check_all_false():
    reason = markers.skip_if_binaries_missing(["python9", "pip9"], check_all=False)
    assert reason is not None
    assert reason == "None of the following binaries was found: python9, pip9"


def test_multiple_missing_check_all_false_with_message():
    reason = markers.skip_if_binaries_missing(["python9", "pip9"], message="Dam!", check_all=False)
    assert reason is not None
    assert reason == "Dam! None of the following binaries was found: python9, pip9"
