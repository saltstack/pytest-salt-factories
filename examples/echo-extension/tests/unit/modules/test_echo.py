import pytest
import salt.modules.test as testmod

import echoext.modules.echo_mod as echo_module


@pytest.fixture
def configure_loader_modules():
    module_globals = {
        "__salt__": {"test.echo": testmod.echo},
    }
    return {
        echo_module: module_globals,
    }


def test_text():
    echo_str = "Echoed!"
    assert echo_module.text(echo_str) == echo_str


def test_reverse():
    echo_str = "Echoed!"
    expected = echo_str[::-1]
    assert echo_module.reverse(echo_str) == expected
