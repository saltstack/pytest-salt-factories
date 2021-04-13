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
    ret = subprocess.run(
        cmdline,
        stdout=subprocess.PIPE,
        universal_newlines=True,
        check=False,
    )
    assert ret.returncode == 0
    assert ret.stdout
    assert ret.stdout.strip() == str(saltfactories.CODE_ROOT_DIR / "utils" / "coverage")
