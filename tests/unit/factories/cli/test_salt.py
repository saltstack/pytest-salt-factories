"""
tests.unit.factories.cli.test_salt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test the ``salt`` CLI functionality
"""
import pytest

from saltfactories.factories.cli.salt import SaltCliFactory


@pytest.fixture
def config_dir(testdir):
    _conf_dir = testdir.mkdir("conf")
    yield _conf_dir
    _conf_dir.remove(rec=1, ignore_errors=True)


@pytest.fixture
def minion_id():
    return "test-minion-id"


@pytest.fixture
def config_file(config_dir, minion_id):
    config_file = config_dir.join("config").strpath
    with open(config_file, "w") as wfh:
        wfh.write("id: {}\n".format(minion_id))
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


def test_missing_minion_id_raises_exception(minion_id, config_dir, config_file, cli_script_name):
    config = {"conf_file": config_file, "id": "the-id"}
    args = ["test.ping"]
    proc = SaltCliFactory(cli_script_name=cli_script_name, config=config)
    with pytest.raises(RuntimeError) as exc:
        proc.build_cmdline(*args)
    assert (
        str(exc.value) == "The `minion_tgt` keyword argument is mandatory for the salt CLI factory"
    )


@pytest.mark.parametrize("flag", ["-V", "--version", "--versions-report", "--help"])
def test_missing_minion_id_does_not_raise_exception(
    minion_id, config_dir, config_file, cli_script_name, flag
):
    """
    Assert that certain flag, which just output something and then exit, don't raise an exception
    """
    config = {"conf_file": config_file, "id": "the-id"}
    args = ["test.ping"] + [flag]
    proc = SaltCliFactory(cli_script_name=cli_script_name, config=config)
    try:
        cmdline = proc.build_cmdline(*args)
    except RuntimeError:
        pytest.fail(
            "The SaltCliFactory raised RuntimeError when the CLI flag '{}' was present in args".format(
                flag
            )
        )
