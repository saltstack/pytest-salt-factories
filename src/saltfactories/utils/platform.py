"""
..
    PYTEST_DONT_REWRITE


saltfactories.utils.platform
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Platform related utilities
"""
import sys

import salt.utils.platform


def is_windows():
    """
    Simple function to return if a host is Windows or not
    :return bool: Return true on Windows
    """
    return salt.utils.platform.is_windows()


def is_linux():
    """
    Simple function to return if a host is Linux or not.
    Note for a proxy minion, we need to return something else
    :return bool: Return true on Linux
    """
    return salt.utils.platform.is_linux()


def is_darwin():
    """
    Simple function to return if a host is Darwin (macOS) or not
    :return bool: Return true on Darwin(macOS)
    """
    return salt.utils.platform.is_darwin()


def is_sunos():
    """
    Simple function to return if host is SunOS or not
    :return bool: Return true on SunOS
    """
    return salt.utils.platform.is_sunos()


def is_smartos():
    """
    Simple function to return if host is SmartOS (Illumos) or not
    :return bool: Return true on SmartOS (Illumos)
    """
    return salt.utils.platform.is_smartos()


def is_freebsd():
    """
    Simple function to return if host is FreeBSD or not
    :return bool: Return true on FreeBSD
    """
    return salt.utils.platform.is_freebsd()


def is_netbsd():
    """
    Simple function to return if host is NetBSD or not
    :return bool: Return true on NetBSD
    """
    return salt.utils.platform.is_netbsd()


def is_openbsd():
    """
    Simple function to return if host is OpenBSD or not
    :return bool: Return true on OpenBSD
    """
    return salt.utils.platform.is_openbsd()


def is_aix():
    """
    Simple function to return if host is AIX or not
    :return bool: Return true on AIX
    """
    return salt.utils.platform.is_aix()


def is_aarch64():
    """
    Simple function to return if host is AArch64 or not
    """
    try:
        return salt.utils.platform.is_aarch64()
    except AttributeError:
        # Salt < 3004
        return sys.platform.startswith("aarch64")


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
    aarch64=False,
):
    """
    Check to see if we're on one of the provided platforms.

    :keyword bool windows: When :py:const:`True`, check if running on Windows.
    :keyword bool linux: When :py:const:`True`, check if running on Linux.
    :keyword bool darwin: When :py:const:`True`, check if running on Darwin.
    :keyword bool sunos: When :py:const:`True`, check if running on SunOS.
    :keyword bool smartos: When :py:const:`True`, check if running on SmartOS.
    :keyword bool freebsd: When :py:const:`True`, check if running on FreeBSD.
    :keyword bool netbsd: When :py:const:`True`, check if running on NetBSD.
    :keyword bool openbsd: When :py:const:`True`, check if running on OpenBSD.
    :keyword bool aix: When :py:const:`True`, check if running on AIX.
    :keyword bool aarch64: When :py:const:`True`, check if running on AArch64.
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

    if aarch64 and is_aarch64():
        return True

    return False
