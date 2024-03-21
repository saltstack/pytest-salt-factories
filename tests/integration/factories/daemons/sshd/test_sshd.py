import shutil
import subprocess

import pytest

from saltfactories.utils import tempfiles

pytestmark = [
    pytest.mark.skip_on_darwin,
    pytest.mark.skip_on_windows,
    pytest.mark.skip_on_salt_system_service,
    pytest.mark.skip_if_binaries_missing("sshd", "ssh-keygen", "ssh-keyscan"),
]


@pytest.fixture(scope="module")
def sshd(salt_factories):
    # Set StrictModes to no because our config directory lives in /tmp and those permissions
    # are not acceptable by sshd strict paranoia.
    sshd_config_dict = {"StrictModes": "no"}
    factory = salt_factories.get_sshd_daemon(sshd_config_dict=sshd_config_dict)
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def known_hosts_file(salt_factories, sshd):
    with tempfiles.temp_file(
        "known_hosts", "\n".join(sshd.get_host_keys()), salt_factories.tmp_root_dir
    ) as known_hosts_file:
        yield known_hosts_file


@pytest.mark.skip_on_windows
def test_sshd(sshd):
    assert sshd.is_running()


@pytest.mark.skip_on_windows
@pytest.mark.skip_if_binaries_missing("ssh")
def test_connect(sshd, known_hosts_file):
    ssh = shutil.which("ssh")
    assert ssh is not None
    cmd = subprocess.run(
        [
            ssh,
            "-i",
            str(sshd.client_key),
            "-p",
            str(sshd.listen_port),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            f"UserKnownHostsFile={known_hosts_file}",
            sshd.listen_address,
            "echo Foo",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert cmd.returncode == 0, cmd
    assert "Foo" in cmd.stdout, cmd
