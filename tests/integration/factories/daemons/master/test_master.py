import pytest
import salt.defaults.exitcodes
from pytestshellutils.exceptions import FactoryNotStarted

from saltfactories.utils import random_string


@pytest.fixture(scope="module")
def master(salt_factories):
    factory = salt_factories.salt_master_daemon(
        random_string("master-"), overrides={"max_open_files": 4096}
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def minion(master):
    factory = master.salt_minion_daemon(random_string("minion-1-"))
    with factory.started():
        yield factory


@pytest.fixture
def minion_3(master):
    factory = master.salt_minion_daemon(random_string("minion-3-"))
    with factory.started():
        yield factory


@pytest.fixture
def salt_run(master, salt_cli_timeout):
    return master.salt_run_cli(timeout=salt_cli_timeout)


@pytest.fixture
def salt_cp(master, salt_cli_timeout):
    return master.salt_cp_cli(timeout=salt_cli_timeout)


@pytest.fixture
def salt_key(master):
    return master.salt_key_cli()


@pytest.fixture
def salt_call(minion, salt_cli_timeout):
    return minion.salt_call_cli(timeout=salt_cli_timeout)


def test_master(master):
    assert master.is_running()


def test_salt_run(master, salt_run):
    max_open_files_config_value = master.config["max_open_files"]
    ret = salt_run.run("config.get", "max_open_files")
    assert ret.returncode == 0, ret
    assert ret.data == max_open_files_config_value


def test_salt_cp_minion_id_as_first_argument(master, minion, salt_cp, tempfiles, tmp_path):
    """
    Test copying a file from the master any minions connected
    """
    dest = tmp_path / "copied-file.txt"
    contents = "id: foo"
    sls = tempfiles.makeslsfile(contents)
    assert master.is_running()
    assert minion.is_running()
    ret = salt_cp.run(minion.id, sls, str(dest))
    assert ret.returncode == 0, ret
    assert ret.data == {minion.id: {str(dest): True}}
    assert dest.is_file()
    assert dest.read_text() == contents


def test_salt_cp_explicit_minion_tgt(master, minion, salt_cp, tempfiles, tmp_path):
    """
    Test copying a file from the master to the minion
    """
    dest = tmp_path / "copied-file.txt"
    contents = "id: foo"
    sls = tempfiles.makeslsfile(contents)
    assert master.is_running()
    assert minion.is_running()
    ret = salt_cp.run(sls, str(dest), minion_tgt=minion.id)
    assert ret.returncode == 0, ret
    assert ret.data == {str(dest): True}
    assert dest.is_file()
    assert dest.read_text() == contents


def test_salt_cp_no_match(master, minion, salt_cp, tempfiles, tmp_path):
    assert master.is_running()
    assert minion.is_running()

    dest = tmp_path / "copied-file.txt"
    contents = "id: foo"
    sls = tempfiles.makeslsfile(contents)
    assert master.is_running()
    assert minion.is_running()
    ret = salt_cp.run(sls, str(dest), minion_tgt="minion-2")
    assert ret.returncode == 0, ret
    assert not ret.data
    assert not dest.is_file()


def test_state_tree(master, salt_call, minion):
    assert minion.is_running()
    sls_contents = """
    test:
      test.succeed_without_changes
    """
    with master.state_tree.base.temp_file("foo.sls", sls_contents):
        ret = salt_call.run("state.sls", "foo")
        assert ret.returncode == 0


@pytest.mark.skip_on_salt_system_service
def test_salt_key(minion, minion_3, salt_key):
    ret = salt_key.run("--list-all")
    assert ret.returncode == 0, ret
    assert ret.data == {
        "minions": [minion.id, minion_3.id],
        "minions_pre": [],
        "minions_denied": [],
        "minions_rejected": [],
    }, ret


@pytest.mark.skip_on_windows
@pytest.mark.skip_on_salt_system_service
def test_exit_status_unknown_user(salt_factories):
    master = salt_factories.salt_master_daemon("set-exitcodes", overrides={"user": "unknown-user"})
    with pytest.raises(FactoryNotStarted) as exc:
        master.start(max_start_attempts=1)

    assert exc.value.process_result.returncode == salt.defaults.exitcodes.EX_NOUSER, str(exc.value)
    assert "The user is not available." in exc.value.process_result.stderr, str(exc.value)
