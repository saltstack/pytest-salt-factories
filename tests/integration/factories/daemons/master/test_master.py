import os
import tempfile

import pytest
import salt.defaults.exitcodes

from saltfactories.exceptions import FactoryNotStarted


@pytest.fixture(scope="module")
def master(request, salt_factories):
    factory = salt_factories.get_salt_master_daemon(
        "master-1", config_overrides={"max_open_files": 4096}
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def minion(request, master):
    factory = master.get_salt_minion_daemon("minion-1")
    with factory.started():
        yield factory


@pytest.fixture
def minion_3(request, master):
    factory = master.get_salt_minion_daemon("minion-3")
    with factory.started():
        yield factory


@pytest.fixture
def salt_run(master):
    return master.get_salt_run_cli()


@pytest.fixture
def salt_cp(master):
    return master.get_salt_cp_cli()


@pytest.fixture
def salt_key(master):
    return master.get_salt_key_cli()


def test_master(master):
    assert master.is_running()


def test_salt_run(master, salt_run):
    max_open_files_config_value = master.config["max_open_files"]
    ret = salt_run.run("config.get", "max_open_files")
    assert ret.exitcode == 0, ret
    assert ret.json == max_open_files_config_value


def test_salt_cp(master, minion, salt_cp, tempfiles):
    """
    Test copying a file from the master to the minion
    """
    tfile = tempfile.NamedTemporaryFile(delete=True)
    tfile.close()
    dest = tfile.name
    try:
        contents = "id: foo"
        sls = tempfiles.makeslsfile(contents)
        assert master.is_running()
        assert minion.is_running()
        ret = salt_cp.run("minion-1", sls, dest)
        assert ret.exitcode == 0, ret
        assert ret.json == {"minion-1": {dest: True}}, ret
        assert os.path.exists(dest)
        with open(dest) as rfh:
            assert rfh.read() == contents
    finally:  # pragma: no cover
        if os.path.exists(dest):
            os.unlink(dest)

    tfile = tempfile.NamedTemporaryFile(delete=True)
    tfile.close()
    dest = tfile.name
    try:
        contents = "id: foo"
        sls = tempfiles.makeslsfile(contents)
        assert master.is_running()
        assert minion.is_running()
        ret = salt_cp.run(sls, dest, minion_tgt="minion-1")
        assert ret.exitcode == 0, ret
        assert ret.json == {dest: True}, ret
        assert os.path.exists(dest)
        with open(dest) as rfh:
            assert rfh.read() == contents
    finally:  # pragma: no cover
        if os.path.exists(dest):
            os.unlink(dest)


def test_salt_cp_no_match(master, minion, salt_cp, tempfiles):
    assert master.is_running()
    assert minion.is_running()

    tfile = tempfile.NamedTemporaryFile(delete=True)
    tfile.close()
    dest = tfile.name
    try:
        contents = "id: foo"
        sls = tempfiles.makeslsfile(contents)
        assert master.is_running()
        assert minion.is_running()
        ret = salt_cp.run(sls, dest, minion_tgt="minion-2")
        assert ret.exitcode == 0, ret
        assert not ret.json, ret
        assert not os.path.exists(dest)
    finally:  # pragma: no cover
        if os.path.exists(dest):
            os.unlink(dest)


def test_salt_key(master, minion, minion_3, salt_key):
    ret = salt_key.run("--list-all")
    assert ret.exitcode == 0, ret
    assert ret.json == {
        "minions": ["minion-1", "minion-3"],
        "minions_pre": [],
        "minions_denied": [],
        "minions_rejected": [],
    }, ret


@pytest.mark.skip_on_windows
def test_exit_status_unknown_user(request, salt_factories):
    master = salt_factories.get_salt_master_daemon(
        "set-exitcodes", config_overrides={"user": "unknown-user"}
    )
    with pytest.raises(FactoryNotStarted) as exc:
        master.start(max_start_attempts=1)

    assert exc.value.exitcode == salt.defaults.exitcodes.EX_NOUSER, str(exc.value)
    assert "The user is not available." in exc.value.stderr, str(exc.value)
