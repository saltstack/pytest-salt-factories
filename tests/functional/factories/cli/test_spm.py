"""
    tests.functional.factories.cli.test_spm
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the ``spm`` CLI functionality
"""
import pathlib


def test_version_info(salt_master, salt_version):
    cli = salt_master.salt_spm_cli()
    ret = cli.run("--version")
    assert ret.exitcode == 0, ret
    assert ret.stdout.strip() == "{} {}".format(pathlib.Path(cli.script_name).name, salt_version)
