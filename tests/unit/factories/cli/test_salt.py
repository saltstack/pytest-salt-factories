"""
Test the ``salt`` CLI functionality.
"""
import shutil

import pytest

from saltfactories.cli.salt import Salt


@pytest.fixture
def config_dir(pytester):
    _conf_dir = pytester.mkdir("conf")
    try:
        yield _conf_dir
    finally:
        shutil.rmtree(str(_conf_dir), ignore_errors=True)


@pytest.fixture
def minion_id():
    return "test-minion-id"


@pytest.fixture
def config_file(config_dir, minion_id):
    config_file = str(config_dir / "config")
    with open(config_file, "w") as wfh:
        wfh.write("id: {}\n".format(minion_id))
    return config_file


@pytest.fixture
def cli_script_name(pytester):
    py_file = pytester.makepyfile(
        """
        print("This would be the CLI script")
        """
    )
    try:
        yield str(py_file)
    finally:
        py_file.unlink()


def test_missing_minion_id_raises_exception(minion_id, config_dir, config_file, cli_script_name):
    config = {"conf_file": config_file, "id": "the-id"}
    args = ["test.ping"]
    proc = Salt(script_name=cli_script_name, config=config)
    with pytest.raises(pytest.UsageError) as exc:
        proc.cmdline(*args)
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
    proc = Salt(script_name=cli_script_name, config=config)
    try:
        proc.cmdline(*args)
    except RuntimeError:
        pytest.fail(
            "The Salt class raised RuntimeError when the CLI flag '{}' was present in args".format(
                flag
            )
        )
