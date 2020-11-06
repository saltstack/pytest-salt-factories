import subprocess

import saltfactories


def test_salt_factories_cli():
    ret = subprocess.run(
        ["salt-factories", "--coverage"],
        stdout=subprocess.PIPE,
        universal_newlines=True,
        check=False,
    )
    assert ret.returncode == 0
    assert ret.stdout
    assert ret.stdout.strip() == str(saltfactories.CODE_ROOT_DIR / "utils" / "coverage")
