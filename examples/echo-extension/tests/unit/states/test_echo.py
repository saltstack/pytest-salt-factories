import pytest
import salt.modules.test as testmod

import echoext.modules.echo_mod as echo_module
import echoext.states.echo_mod as echo_state


@pytest.fixture
def configure_loader_modules():
    return {
        echo_module: {
            "__salt__": {
                "test.echo": testmod.echo,
            },
        },
        echo_state: {
            "__salt__": {
                "echo.text": echo_module.text,
                "echo.reverse": echo_module.reverse,
            },
        },
    }


def test_echoed():
    echo_str = "Echoed!"
    expected = {
        "name": echo_str,
        "changes": {},
        "result": True,
        "comment": "The 'echo.echoed' returned: '{}'".format(echo_str),
    }
    assert echo_state.echoed(echo_str) == expected


def test_reversed():
    echo_str = "Echoed!"
    expected_str = echo_str[::-1]
    expected = {
        "name": echo_str,
        "changes": {},
        "result": True,
        "comment": "The 'echo.reversed' returned: '{}'".format(expected_str),
    }
    assert echo_state.reversed(echo_str) == expected
