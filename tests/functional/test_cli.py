import shutil
import subprocess
import sys

import pytest

import saltfactories


def cmdline_ids(value):
    if value[0] == sys.executable:
        return " ".join(["python"] + value[1:])
    return " ".join(value)


@pytest.mark.parametrize(
    "cmdline",
    (
        ["salt-factories", "--coverage"],
        [sys.executable, "-m", "saltfactories", "--coverage"],
    ),
    ids=cmdline_ids,
)
def test_salt_factories_cli(cmdline):
    if not shutil.which(cmdline[0]):  # pragma: no cover
        pytest.skip(f"binary {cmdline[0]} not found")
    ret = subprocess.run(
        cmdline,
        stdout=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert ret.returncode == 0
    assert ret.stdout
    assert ret.stdout.strip() == str(saltfactories.CODE_ROOT_DIR / "utils" / "coverage")


@pytest.mark.parametrize(
    "cmdline",
    (
        ["salt-factories"],
        [sys.executable, "-m", "saltfactories"],
    ),
    ids=cmdline_ids,
)
def test_salt_factories_cli_show_help(cmdline):
    if not shutil.which(cmdline[0]):  # pragma: no cover
        pytest.skip(f"binary {cmdline[0]} not found")
    ret = subprocess.run(
        cmdline,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ret.returncode == 1
    assert not ret.stdout
    assert ret.stderr
    assert "usage:" in ret.stderr.strip()
