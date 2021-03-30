import pytest

pytestmark = [
    pytest.mark.requires_salt_states("echo.text"),
]


def test_echoed(salt_call_cli):
    echo_str = "Echoed!"
    ret = salt_call_cli.run("state.single", "echo.echoed", echo_str)
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json == echo_str


def test_reversed(salt_call_cli):
    echo_str = "Echoed!"
    expected = echo_str[::-1]
    ret = salt_call_cli.run("state.single", "echo.reversed", echo_str)
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json == expected
