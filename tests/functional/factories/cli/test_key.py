"""
    tests.functional.factories.cli.test_key
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the ``salt-key`` CLI functionality
"""
import pathlib


def test_version_info(salt_factories, salt_master_config, salt_version):
    cli = salt_factories.get_salt_key_cli(salt_master_config["id"])
    ret = cli.run("--version")
    assert ret.exitcode == 0, ret
    assert ret.stdout.strip() == "{} {}".format(
        pathlib.Path(cli.cli_script_name).name, salt_version
    )
