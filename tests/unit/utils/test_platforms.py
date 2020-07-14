"""
    tests.unit.utils.test_platforms
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Tests for saltfactories.utils.platforms
"""
from unittest import mock

import saltfactories.utils.platform


def test_is_windows():
    return_value = True
    with mock.patch("salt.utils.platform.is_windows", return_value=return_value):
        assert saltfactories.utils.platform.is_windows() is return_value


def test_is_not_windows():
    return_value = True
    with mock.patch("salt.utils.platform.is_windows", return_value=return_value):
        assert saltfactories.utils.platform.is_windows() is return_value


def test_is_linux():
    return_value = True
    with mock.patch("salt.utils.platform.is_linux", return_value=return_value):
        assert saltfactories.utils.platform.is_linux() is return_value


def test_is_not_linux():
    return_value = True
    with mock.patch("salt.utils.platform.is_linux", return_value=return_value):
        assert saltfactories.utils.platform.is_linux() is return_value


def test_is_darwin():
    return_value = True
    with mock.patch("salt.utils.platform.is_darwin", return_value=return_value):
        assert saltfactories.utils.platform.is_darwin() is return_value


def test_is_not_darwin():
    return_value = True
    with mock.patch("salt.utils.platform.is_darwin", return_value=return_value):
        assert saltfactories.utils.platform.is_darwin() is return_value


def test_is_sunos():
    return_value = True
    with mock.patch("salt.utils.platform.is_sunos", return_value=return_value):
        assert saltfactories.utils.platform.is_sunos() is return_value


def test_is_not_sunos():
    return_value = True
    with mock.patch("salt.utils.platform.is_sunos", return_value=return_value):
        assert saltfactories.utils.platform.is_sunos() is return_value


def test_is_smartos():
    return_value = True
    with mock.patch("salt.utils.platform.is_smartos", return_value=return_value):
        assert saltfactories.utils.platform.is_smartos() is return_value


def test_is_not_smartos():
    return_value = True
    with mock.patch("salt.utils.platform.is_smartos", return_value=return_value):
        assert saltfactories.utils.platform.is_smartos() is return_value


def test_is_freebsd():
    return_value = True
    with mock.patch("salt.utils.platform.is_freebsd", return_value=return_value):
        assert saltfactories.utils.platform.is_freebsd() is return_value


def test_is_not_freebsd():
    return_value = True
    with mock.patch("salt.utils.platform.is_freebsd", return_value=return_value):
        assert saltfactories.utils.platform.is_freebsd() is return_value


def test_is_netbsd():
    return_value = True
    with mock.patch("salt.utils.platform.is_netbsd", return_value=return_value):
        assert saltfactories.utils.platform.is_netbsd() is return_value


def test_is_not_netbsd():
    return_value = True
    with mock.patch("salt.utils.platform.is_netbsd", return_value=return_value):
        assert saltfactories.utils.platform.is_netbsd() is return_value


def test_is_openbsd():
    return_value = True
    with mock.patch("salt.utils.platform.is_openbsd", return_value=return_value):
        assert saltfactories.utils.platform.is_openbsd() is return_value


def test_is_not_openbsd():
    return_value = True
    with mock.patch("salt.utils.platform.is_openbsd", return_value=return_value):
        assert saltfactories.utils.platform.is_openbsd() is return_value


def test_is_aix():
    return_value = True
    with mock.patch("salt.utils.platform.is_aix", return_value=return_value):
        assert saltfactories.utils.platform.is_aix() is return_value


def test_is_not_aix():
    return_value = True
    with mock.patch("salt.utils.platform.is_aix", return_value=return_value):
        assert saltfactories.utils.platform.is_aix() is return_value
