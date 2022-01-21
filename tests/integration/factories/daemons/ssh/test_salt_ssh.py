import logging
import textwrap

import pytest

from saltfactories.utils import random_string

log = logging.getLogger(__name__)


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
    roster_file_path = salt_factories.tmp_root_dir / "salt_ssh_roster"
    with open(str(roster_file_path), "w") as wfh:
        contents = textwrap.dedent(
            """\
        localhost:
          host: 127.0.0.1
          port: {}
          mine_functions:
            test.arg: ['itworked']
        """.format(
                sshd.listen_port
            )
        )
        wfh.write(contents)
        log.debug("Wrote '%s' with contents:\n%s", roster_file_path, contents)
        log.warning("")
    try:
        yield master.salt_ssh_cli(
            roster_file=str(roster_file_path), client_key=str(sshd.client_key)
        )
    finally:
        roster_file_path.unlink()


@pytest.mark.skip_on_windows
def test_salt_ssh(salt_ssh_cli):
    ret = salt_ssh_cli.run("--ignore-host-keys", "test.echo", "It Works!", minion_tgt="localhost")
    assert ret.returncode == 0
    assert ret.data == "It Works!"
