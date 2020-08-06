"""
    tests.functional.factories.cli.test_run
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the ``salt-run`` CLI functionality
"""
import pathlib


def test_version_info(salt_master, salt_version):
    cli = salt_master.get_salt_run_cli()
    ret = cli.run("--version")
    assert ret.exitcode == 0, ret
    assert ret.stdout.strip() == "{} {}".format(
        pathlib.Path(cli.cli_script_name).name, salt_version
    )
