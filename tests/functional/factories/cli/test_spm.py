"""
Test the ``spm`` CLI functionality.
"""
import pathlib

import pytest


@pytest.fixture
def spm_formulas_dir(salt_master):
    formula_sls = """
    install-apache:
      pkg.installed:
        - name: apache2
    """
    formula = """
     name: apache
     os: RedHat, Debian, Ubuntu, Suse, FreeBSD
     os_family: RedHat, Debian, Suse, FreeBSD
     version: 201506
     release: 2
     summary: Formula for installing Apache
     description: Formula for installing Apache
    """
    with salt_master.state_tree.base.temp_file(
        "formulas/apache/apache.sls", formula_sls
    ), salt_master.state_tree.base.temp_file("formulas/FORMULA", formula):
        yield salt_master.state_tree.base.write_path / "formulas"


def test_version_info(salt_master, salt_version):
    cli = salt_master.salt_spm_cli()
    ret = cli.run("--version")
    assert ret.returncode == 0, ret
    assert ret.stdout.strip() == "{} {}".format(pathlib.Path(cli.script_name).name, salt_version)


def test_build_and_install(salt_master, spm_formulas_dir):
    cli = salt_master.salt_spm_cli()
    spm_build_dir = pathlib.Path(cli.config["spm_build_dir"])
    formula_path = pathlib.Path(cli.config["formula_path"])
    ret = cli.run(
        "build",
        str(spm_formulas_dir),
    )
    assert ret.returncode == 0

    ret = cli.run(
        "install",
        str(spm_build_dir / "apache-201506-2.spm"),
        "-y",
    )
    assert ret.returncode == 0
    assert formula_path.joinpath("apache", "apache.sls").exists()
