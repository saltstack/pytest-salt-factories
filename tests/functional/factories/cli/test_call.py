"""
    tests.functional.factories.cli.test_call
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the ``salt-call`` CLI functionality
"""
import pathlib


def test_version_info(salt_factories, salt_minion, salt_proxy_minion, salt_version):
    cli = salt_factories.get_salt_call_cli(salt_minion.id)
    ret = cli.run("--version")
    assert ret.exitcode == 0, ret
    assert ret.stdout.strip() == "{} {}".format(
        pathlib.Path(cli.cli_script_name).name, salt_version
    )
    cli = salt_factories.get_salt_call_cli(salt_proxy_minion.id)
    ret = cli.run("--version")
    assert ret.exitcode == 0, ret
    assert ret.stdout.strip() == "{} {}".format(
        pathlib.Path(cli.cli_script_name).name, salt_version
    )


def test_version_through_proxied_method(request, salt_minion, salt_proxy_minion, salt_version):
    cli = salt_minion.get_salt_call_cli()
    ret = cli.run("--version")
    assert ret.exitcode == 0, ret
    assert ret.stdout.strip() == "{} {}".format(
        pathlib.Path(cli.cli_script_name).name, salt_version
    )
    cli = salt_proxy_minion.get_salt_call_cli()
    ret = cli.run("--version")
    assert ret.exitcode == 0, ret
    assert ret.stdout.strip() == "{} {}".format(
        pathlib.Path(cli.cli_script_name).name, salt_version
    )
