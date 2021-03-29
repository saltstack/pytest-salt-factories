__virtualname__ = "echo"


def __virtual__():
    return __virtualname__


def text(string):
    """
    This function just returns any text that it's given.

    CLI Example:

    .. code-block:: bash

        salt '*' echo.text 'foo bar baz quo qux'
    """
    return __salt__["test.echo"](string)


def reverse(string):
    """
    This function just returns any text that it's given, reversed.

    CLI Example:

    .. code-block:: bash

        salt '*' echo.reverse 'foo bar baz quo qux'
    """
    return __salt__["test.echo"](string)[::-1]
