"""
    tests.unit.utils.test_platform
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Tests for saltfactories.utils.platform
"""
import subprocess
from unittest import mock

import pytest

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


def test_is_aarch64():
    return_value = True
    with mock.patch("sys.platform", "aarch64"):
        assert saltfactories.utils.platform.is_aarch64() is return_value


def test_is_not_aarch64():
    return_value = False
    with mock.patch("sys.platform", "not_aarch64"):
        assert saltfactories.utils.platform.is_aarch64() is return_value


def test_is_fips_enabled_etc_system_fips(fs):
    fs.create_file("/etc/system-fips")
    assert saltfactories.utils.platform.is_fips_enabled() is True


@pytest.mark.parametrize("value, expected", [("0", False), ("1", True)])
def test_is_fips_enabled_procfs(fs, value, expected):
    fs.create_file("/proc/sys/crypto/fips_enabled", contents=value)
    assert saltfactories.utils.platform.is_fips_enabled() is expected


@pytest.mark.parametrize(
    "output, expected",
    (
        ("", False),
        ("crypto.fips_enabled", False),
        ("crypto.fips_enabled =", False),
        ("crypto.fips_enabled = 0", False),
        ("crypto.fips_enabled=1", True),
        ("crypto.fips_enabled = 1", True),
        ("crypto.fips_enabled =  1", True),
    ),
)
def test_is_fips_enabled_sysctl(output, expected):
    subprocess_run_return_value = subprocess.CompletedProcess(
        args=(), returncode=0, stdout=output, stderr=None
    )
    with mock.patch("shutil.which", return_value="sysctl"), mock.patch(
        "subprocess.run", return_value=subprocess_run_return_value
    ):
        assert saltfactories.utils.platform.is_fips_enabled() is expected
