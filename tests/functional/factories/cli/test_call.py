"""
    tests.functional.factories.cli.test_call
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the ``salt-call`` CLI functionality
"""
import pathlib


def test_version_info(salt_factories, salt_minion_config, salt_version):
    cli = salt_factories.get_salt_call_cli(salt_minion_config["id"])
    ret = cli.run("--version")
    assert ret.exitcode == 0, ret
    assert ret.stdout.strip() == "{} {}".format(
        pathlib.Path(cli.cli_script_name).name, salt_version
    )
