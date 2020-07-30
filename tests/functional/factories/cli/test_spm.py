"""
    tests.functional.factories.cli.test_spm
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the ``spm`` CLI functionality
"""
import pathlib


def test_version_info(salt_factories, salt_master, salt_version):
    cli = salt_factories.get_salt_spm_cli(salt_master.id)
    ret = cli.run("--version")
    assert ret.exitcode == 0, ret
    assert ret.stdout.strip() == "{} {}".format(
        pathlib.Path(cli.cli_script_name).name, salt_version
    )


def test_version_through_proxied_method(salt_master, salt_version):
    cli = salt_master.get_salt_spm_cli()
    ret = cli.run("--version")
    assert ret.exitcode == 0, ret
    assert ret.stdout.strip() == "{} {}".format(
        pathlib.Path(cli.cli_script_name).name, salt_version
    )
