import sys

import pytest

from saltfactories.factories.base import SaltDaemonFactory


@pytest.fixture
def config_dir(testdir):
    _conf_dir = testdir.mkdir("conf")
    yield _conf_dir
    _conf_dir.remove(rec=1, ignore_errors=True)


@pytest.fixture
def master_id():
    return "test-master-id"


@pytest.fixture
def config_file(config_dir, master_id):
    config_file = config_dir.join("config").strpath
    with open(config_file, "w") as wfh:
        wfh.write("id: {}\n".format(master_id))
    return config_file


@pytest.fixture
def cli_script_name(testdir):
    py_file = testdir.makepyfile(
        """
        print("This would be the CLI script")
        """
    )
    yield py_file.strpath
    py_file.remove(rec=0, ignore_errors=True)


def test_default_cli_flags(config_dir, config_file, cli_script_name):
    config = {"conf_file": config_file, "id": "the-id"}
    expected = [
        sys.executable,
        cli_script_name,
        "--config-dir={}".format(config_dir.strpath),
        "--log-level=critical",
    ]
    proc = SaltDaemonFactory(start_timeout=1, cli_script_name=cli_script_name, config=config)
    cmdline = proc.build_cmdline()
    assert cmdline == expected


@pytest.mark.parametrize("flag", ["-l", "--log-level", "--log-level="])
def test_override_log_level(config_dir, config_file, cli_script_name, flag):
    config = {"conf_file": config_file, "id": "the-id"}
    if flag.endswith("="):
        args = [flag + "info"]
    else:
        args = [flag, "info"]

    expected = [
        sys.executable,
        cli_script_name,
        "--config-dir={}".format(config_dir.strpath),
    ] + args
    proc = SaltDaemonFactory(start_timeout=1, cli_script_name=cli_script_name, config=config)
    cmdline = proc.build_cmdline(*args)
    assert cmdline == expected


@pytest.mark.parametrize("flag", ["-c", "--config-dir", "--config-dir=", None])
def test_override_config_dir(config_dir, config_file, cli_script_name, flag):
    passed_config_dir = config_dir.strpath + ".new"
    if flag is None:
        args = ["--config-dir={}".format(config_dir.strpath)]
    elif flag.endswith("="):
        args = [flag + passed_config_dir]
    else:
        args = [flag, passed_config_dir]

    config = {"conf_file": config_file, "id": "the-id"}
    expected = [sys.executable, cli_script_name, "--log-level=critical"] + args
    proc = SaltDaemonFactory(start_timeout=1, cli_script_name=cli_script_name, config=config)
    cmdline = proc.build_cmdline(*args)
    assert cmdline == expected


def test_salt_daemon_factory_id_attr_comes_first_in_repr(config_file):
    proc = SaltDaemonFactory(
        start_timeout=1, cli_script_name="foo-bar", config={"id": "TheID", "conf_file": config_file}
    )
    regex = r"{}(id='TheID'".format(proc.__class__.__name__)
    assert repr(proc).startswith(regex)
    assert str(proc).startswith(regex)


def test_salt_cli_display_name(config_file):
    factory_id = "TheID"
    proc = SaltDaemonFactory(
        start_timeout=1,
        cli_script_name="foo-bar",
        config={"id": factory_id, "conf_file": config_file},
    )
    assert proc.get_display_name() == "{}(id={!r})".format(SaltDaemonFactory.__name__, factory_id)
