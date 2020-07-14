import pytest


@pytest.fixture(scope="module")
def sshd(request, salt_factories):
    return salt_factories.spawn_sshd_server(request, "sshd")


@pytest.mark.skip_on_windows
@pytest.mark.skip_if_binaries_missing("sshd", "ssh-keygen")
def test_sshd(sshd):
    assert sshd.is_alive()
