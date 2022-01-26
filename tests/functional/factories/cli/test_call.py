"""
Test the ``salt-call`` CLI functionality.
"""
import pathlib


def test_version_info(salt_minion, salt_proxy_minion, salt_version):
    cli = salt_minion.salt_call_cli()
    ret = cli.run("--version")
    assert ret.returncode == 0, ret
    assert ret.stdout.strip() == "{} {}".format(pathlib.Path(cli.script_name).name, salt_version)
    cli = salt_proxy_minion.salt_call_cli()
    ret = cli.run("--version")
    assert ret.returncode == 0, ret
    assert ret.stdout.strip() == "{} {}".format(pathlib.Path(cli.script_name).name, salt_version)
