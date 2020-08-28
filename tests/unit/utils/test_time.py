import time
from unittest import mock

import saltfactories.utils.time


def test_sleep():
    start = time.time()
    with mock.patch("time.sleep", return_value=None):
        time.sleep(1)
        saltfactories.utils.time.sleep(0.1)
    end = time.time()
    duration = end - start
    assert duration >= 0.1  # We did sleep 0.1 second
    assert duration < 0.5  # But the patched time.sleep was mocked
