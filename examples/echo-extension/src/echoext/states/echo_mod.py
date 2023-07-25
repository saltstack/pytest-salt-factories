__virtualname__ = "echo"


def __virtual__():
    if "echo.text" not in __salt__:
        return False, "The 'echo' execution module is not available"
    return __virtualname__


def echoed(name):
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    value = __salt__["echo.text"](name)
    if value == name:
        ret["result"] = True
        ret["comment"] = f"The 'echo.echoed' returned: '{value}'"
    return ret


def reversed(name):
    """
    This example function should be replaced
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    value = __salt__["echo.reverse"](name)
    if value == name[::-1]:
        ret["result"] = True
        ret["comment"] = f"The 'echo.reversed' returned: '{value}'"
    return ret
