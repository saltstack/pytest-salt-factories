import shutil
import subprocess

import pytest

pytestmark = [
    pytest.mark.skip_on_darwin,
    pytest.mark.skip_on_windows,
    pytest.mark.skip_on_salt_system_service,
]


@pytest.fixture(scope="module")
@pytest.mark.skip_if_binaries_missing("sshd", "ssh-keygen")
def sshd(salt_factories):
    # Set StrictModes to no because our config directory lives in /tmp and those permissions
    # are not acceptable by sshd strict paranoia.
    sshd_config_dict = {"StrictModes": "no"}
    factory = salt_factories.get_sshd_daemon(sshd_config_dict=sshd_config_dict)
    with factory.started():
        yield factory


@pytest.mark.skip_on_windows
def test_sshd(sshd):
    assert sshd.is_running()


@pytest.mark.skip_on_windows
@pytest.mark.skip_if_binaries_missing("ssh")
def test_connect(sshd):
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
            "UserKnownHostsFile=/dev/null",
            sshd.listen_address,
            "echo Foo",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert cmd.returncode == 0, cmd
    assert "Foo" in cmd.stdout, cmd
