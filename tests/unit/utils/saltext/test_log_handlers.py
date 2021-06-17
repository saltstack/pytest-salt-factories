import pytest

from saltfactories.utils.saltext.log_handlers.pytest_log_handler import ZMQHandler


def test_zmqhandler_immutable_formatter_attribute(subtests):
    handler = ZMQHandler()
    formatter = handler.formatter

    with subtests.test("ZMQHandler.setFormatter()"):
        with pytest.raises(RuntimeError):
            handler.setFormatter("foo")

    with subtests.test("ZMQHandler.formatter = ..."):
        with pytest.raises(RuntimeError):
            handler.formatter = "foo"

    with subtests.test("del ZMQHandler.formatter"):
        with pytest.raises(RuntimeError):
            del handler.formatter

    assert handler.formatter is formatter
