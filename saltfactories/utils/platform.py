"""
..
    PYTEST_DONT_REWRITE


saltfactories.utils.platform
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Platform related utilities
"""
import salt.utils.platform


def is_windows():
    """
    Simple function to return if a host is Windows or not
    """
    return salt.utils.platform.is_windows()


def is_linux():
    """
    Simple function to return if a host is Linux or not.
    Note for a proxy minion, we need to return something else
    """
    return salt.utils.platform.is_linux()


def is_darwin():
    """
    Simple function to return if a host is Darwin (macOS) or not
    """
    return salt.utils.platform.is_darwin()


def is_sunos():
    """
    Simple function to return if host is SunOS or not
    """
    return salt.utils.platform.is_sunos()


def is_smartos():
    """
    Simple function to return if host is SmartOS (Illumos) or not
    """
    return salt.utils.platform.is_smartos()


def is_freebsd():
    """
    Simple function to return if host is FreeBSD or not
    """
    return salt.utils.platform.is_freebsd()


def is_netbsd():
    """
    Simple function to return if host is NetBSD or not
    """
    return salt.utils.platform.is_netbsd()


def is_openbsd():
    """
    Simple function to return if host is OpenBSD or not
    """
    return salt.utils.platform.is_openbsd()


def is_aix():
    """
    Simple function to return if host is AIX or not
    """
    return salt.utils.platform.is_aix()


def on_platforms(
    windows=False,
    linux=False,
    darwin=False,
    sunos=False,
    smartos=False,
    freebsd=False,
    netbsd=False,
    openbsd=False,
    aix=False,
):
    """
    Check to see if we're on one of the provided platforms.
    """
    if windows and is_windows():
        return True

    if linux and is_linux():
        return True

    if darwin and is_darwin():
        return True

    if sunos and is_sunos():
        return True

    if smartos and is_smartos():
        return True

    if freebsd and is_freebsd():
        return True

    if netbsd and is_netbsd():
        return True

    if openbsd and is_openbsd():
        return True

    if aix and is_aix():
        return True

    return False
