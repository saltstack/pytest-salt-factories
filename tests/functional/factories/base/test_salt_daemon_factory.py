import pytest

from saltfactories.exceptions import FactoryNotStarted
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


def test_extra_cli_arguments_after_first_failure(
    request, config_dir, config_file, tempfiles, master_id, tmpdir
):
    """
    This test asserts that after the first start failure, the extra_cli_arguments_after_first_start_failure arguments
    are added
    """
    output_file = tmpdir.join("output.txt")
    config = {"conf_file": config_file, "id": master_id}
    script = tempfiles.makepyfile(
        r"""
        # coding=utf-8

        import sys
        import multiprocessing

        def main():
            with open({!r}, "a") as wfh:
                wfh.write(" ".join(sys.argv))
                wfh.write("\n")
            sys.exit(1)

        # Support for windows test runs
        if __name__ == '__main__':
            multiprocessing.freeze_support()
            main()
        """.format(
            output_file.strpath
        ),
        executable=True,
    )
    daemon = SaltDaemonFactory(
        cli_script_name=script,
        config=config,
        start_timeout=0.25,
        max_start_attempts=2,
        check_ports=[12345],
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    # Make sure the daemon is terminated no matter what
    request.addfinalizer(daemon.terminate)
    with pytest.raises(FactoryNotStarted):
        daemon.start()
    output_file_contents = output_file.read().splitlines()
    expected = [
        "{} --config-dir={} --log-level=critical".format(script, config_dir.strpath),
        "{} --config-dir={} --log-level=debug".format(script, config_dir.strpath),
    ]
    assert output_file_contents == expected
