import subprocess

import pytest


@pytest.fixture(scope="module")
@pytest.mark.skip_if_binaries_missing("sshd", "ssh-keygen")
def sshd(request, salt_factories):
    # Set StrictModes to no because our config directory lives in /tmp and those permissions
    # are not acceptable by sshd strict paranoia.
    sshd_config_dict = {"StrictModes": "no"}
    factory = salt_factories.get_sshd_daemon("sshd", sshd_config_dict=sshd_config_dict)
    with factory.started():
        yield factory


@pytest.mark.skip_on_windows
def test_sshd(sshd):
    assert sshd.is_running()


@pytest.mark.skip_on_windows
@pytest.mark.skip_if_binaries_missing("ssh")
def test_connect(sshd):
    cmd = subprocess.run(
        [
            "ssh",
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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        check=False,
    )
    assert cmd.returncode == 0, cmd
    assert "Foo" in cmd.stdout, cmd
