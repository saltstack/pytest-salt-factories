"""
Test the ``salt-cp`` CLI functionality.
"""
import pathlib


def test_version_info(salt_master, salt_version):
    cli = salt_master.salt_cp_cli()
    ret = cli.run("--version")
    assert ret.returncode == 0, ret
    assert ret.stdout.strip() == "{} {}".format(pathlib.Path(cli.script_name).name, salt_version)
