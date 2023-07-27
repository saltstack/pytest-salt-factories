import shutil

import attr
import pytest
import importlib_metadata

from saltfactories import CODE_ROOT_DIR
from saltfactories.utils.virtualenv import VirtualEnv


@attr.s(kw_only=True, slots=True, frozen=True)
class ExtensionVirtualEnv(VirtualEnv):
    extension_path = attr.ib()
    tmp_path = attr.ib()
    copy_path = attr.ib(init=False)
    venv = attr.ib(init=False)

    @copy_path.default
    def _default_copy_path(self):
        _copy_path = self.tmp_path / "code"
        shutil.copytree(str(self.extension_path), str(_copy_path))
        return _copy_path

    @venv.default
    def _init_virtualenv(self):
        return VirtualEnv(self.tmp_path / ".venv", cwd=self.copy_path)

    def __enter__(self):  # noqa: D105
        self.venv.__enter__()
        self.venv.run("git", "init", ".")
        self.venv.run("git", "add", ".")

        import salt.version  # pylint: disable=import-outside-toplevel

        self.venv.install(f"salt=={salt.version.__saltstack_version__}")
        self.venv.install(f"pytest=={importlib_metadata.version('pytest')}")
        self.venv.install(str(CODE_ROOT_DIR.parent.parent))

        if salt.version.__saltstack_version__ < "3006":
            # Only Salt >= 3006 supports importlib-metadata>=5.0.0
            self.venv.install("importlib-metadata<5.0.0")
        self.venv.install(".[tests]")
        return self.venv

    def __exit__(self, *_):  # noqa: D105
        self.venv.__exit__(*_)


@pytest.fixture
def extension_venv(tmp_path):
    def create_extension_virtualenv(extension_path):
        return ExtensionVirtualEnv(extension_path=extension_path, tmp_path=tmp_path)

    return create_extension_virtualenv
