"""
Test the ``salt-run`` CLI functionality.
"""
import pathlib


def test_version_info(salt_master, cli_salt_version):
    cli = salt_master.salt_run_cli()
    ret = cli.run("--version")
    assert ret.returncode == 0, ret
    assert ret.stdout.strip() == f"{pathlib.Path(cli.script_name).name} {cli_salt_version}"
