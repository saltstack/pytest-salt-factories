"""
    tests.functional.factories.cli.test_cloud
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the ``salt-cloud`` CLI functionality
"""
import pathlib


def test_version_info(request, salt_factories, salt_master, salt_version):
    cli = salt_factories.get_salt_cloud_cli(request, salt_master.id)
    ret = cli.run("--version")
    assert ret.exitcode == 0, ret
    assert ret.stdout.strip() == "{} {}".format(
        pathlib.Path(cli.cli_script_name).name, salt_version
    )


def test_version_through_proxied_method(request, salt_master, salt_version):
    cli = salt_master.get_salt_cloud_cli(request)
    ret = cli.run("--version")
    assert ret.exitcode == 0, ret
    assert ret.stdout.strip() == "{} {}".format(
        pathlib.Path(cli.cli_script_name).name, salt_version
    )
