import pytest

pytestmark = [
    pytest.mark.requires_salt_modules("echo.text"),
]


def test_text(salt_call_cli):
    echo_str = "Echoed!"
    ret = salt_call_cli.run("echo.text", echo_str)
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json == echo_str


def test_reverse(salt_call_cli):
    echo_str = "Echoed!"
    expected = echo_str[::-1]
    ret = salt_call_cli.run("echo.reverse", echo_str)
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json == expected
