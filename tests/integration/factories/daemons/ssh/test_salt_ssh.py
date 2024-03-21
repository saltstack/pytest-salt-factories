import logging

import pytest

from saltfactories.utils import random_string
from saltfactories.utils import tempfiles

log = logging.getLogger(__name__)

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


@pytest.fixture(scope="module")
def master(salt_factories):
    return salt_factories.salt_master_daemon(random_string("master-"))


@pytest.fixture(scope="module")
def salt_ssh_cli(sshd, salt_factories, master):
    roster_file_contents = f"""
    localhost:
        host: 127.0.0.1
        port: {sshd.listen_port}
        mine_functions:
        test.arg: ['itworked']
    """
    # pylint: disable=no-member
    with tempfiles.temp_file(
        "salt_ssh_roster", roster_file_contents, salt_factories.tmp_root_dir
    ) as roster_file_path, tempfiles.temp_file(
        "known_hosts", "\n".join(sshd.get_host_keys()), salt_factories.tmp_root_dir
    ) as known_hosts_file, tempfiles.temp_file(
        "master.d/known-hosts.conf", f"known_hosts_file: {known_hosts_file}\n", master.config_dir
    ):
        yield master.salt_ssh_cli(
            roster_file=str(roster_file_path), client_key=str(sshd.client_key)
        )
    # pylint: enable=no-member


@pytest.mark.skip_on_windows
def test_salt_ssh(salt_ssh_cli):
    ret = salt_ssh_cli.run("test.echo", "It Works!", minion_tgt="localhost")
    assert ret.returncode == 0
    assert ret.data == "It Works!"
