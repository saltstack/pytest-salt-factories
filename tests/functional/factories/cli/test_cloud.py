"""
    tests.functional.factories.cli.test_cloud
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the ``salt-cloud`` CLI functionality
"""
import pathlib


def test_version_info(request, salt_factories, salt_master_config, salt_version):
    cli = salt_factories.get_salt_cloud_cli(request, salt_master_config["id"])
    ret = cli.run("--version")
    assert ret.exitcode == 0, ret
    assert ret.stdout.strip() == "{} {}".format(
        pathlib.Path(cli.cli_script_name).name, salt_version
    )
