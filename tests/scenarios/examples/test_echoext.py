from saltfactories import CODE_ROOT_DIR


def test_echoext(extension_venv):
    extension_path = CODE_ROOT_DIR.parent.parent / "examples" / "echo-extension"
    with extension_venv(extension_path) as venv:
        ret = venv.run(venv.venv_python, "-m", "pytest", str(extension_path), check=False)
        assert ret.returncode == 0
