import functools
import logging
import os
import pathlib
import stat
import tempfile
import textwrap

import pytest
import salt.version

log = logging.getLogger(__name__)

TESTS_PATH = pathlib.Path(__file__).resolve().parent


try:  # pragma: no cover
    import importlib.metadata

    pkg_version = importlib.metadata.version  # pylint: disable=no-member
except ImportError:  # pragma: no cover
    try:
        import importlib_metadata

        pkg_version = importlib_metadata.version
    except ImportError:  # pragma: no cover
        import pkg_resources

        def pkg_version(package):
            return pkg_resources.get_distribution(package).version


# Define the pytest plugins we rely on
pytest_plugins = ["helpers_namespace"]


def pkg_version_info(package):
    return tuple(int(part) for part in pkg_version(package).split(".") if part.isdigit())


if pkg_version_info("pytest") >= (6, 2):
    pytest_plugins.append("pytester")
else:

    @pytest.fixture
    def pytester():
        pytest.skip("The pytester fixture is not available in Pytest < 6.2.0")


def pytest_report_header():
    return "salt-version: {}".format(salt.version.__version__)


class Tempfiles:
    """
    Class which generates temporary files and cleans them when done
    """

    def __init__(self, request):
        self.request = request

    def makepyfile(self, contents, prefix=None, executable=False):
        """
        Creates a python file and returns it's path
        """
        tfile = tempfile.NamedTemporaryFile("w", prefix=prefix or "tmp", suffix=".py", delete=False)
        contents = textwrap.dedent(contents.lstrip("\n")).strip()
        tfile.write(contents)
        tfile.close()
        if executable is True:
            _stat = os.stat(tfile.name)
            os.chmod(tfile.name, _stat.st_mode | stat.S_IEXEC)
        self.request.addfinalizer(functools.partial(self._delete_temp_file, tfile.name))
        with open(tfile.name, encoding="utf-8") as rfh:
            log.debug(
                "Created python file with contents:\n>>>>> %s >>>>>\n%s\n<<<<< %s <<<<<\n",
                tfile.name,
                rfh.read(),
                tfile.name,
            )
        return tfile.name

    def makeslsfile(self, contents, name=None):
        """
        Creates an sls file and returns it's path
        """
        if name is None:
            tfile = tempfile.NamedTemporaryFile("w", suffix=".sls", delete=False)
            name = tfile.name
        with open(name, "w", encoding="utf-8") as wfh:
            contents = textwrap.dedent(contents.lstrip("\n")).strip()
            wfh.write(contents)
        self.request.addfinalizer(functools.partial(self._delete_temp_file, name))
        with open(name, encoding="utf-8") as rfh:
            log.debug(
                "Created SLS file with contents:\n>>>>> %s >>>>>\n%s\n<<<<< %s <<<<<\n",
                name,
                rfh.read(),
                name,
            )
        return name

    def _delete_temp_file(self, fpath):
        """
        Cleanup the temporary path
        """
        if os.path.exists(fpath):
            os.unlink(fpath)


@pytest.fixture
def tempfiles(request):
    """
    Temporary files fixture
    """
    return Tempfiles(request)


@pytest.fixture(scope="session")
def salt_version():
    return pkg_version("salt")


def pytest_collection_modifyitems(items):
    system_service_skip_paths = (
        # There's no point on running these tests against a system install of salt
        str(TESTS_PATH / "unit"),
        str(TESTS_PATH / "functional"),
        str(TESTS_PATH / "scenarios" / "examples"),
        str(TESTS_PATH / "integration" / "factories" / "cli"),
        str(TESTS_PATH / "integration" / "factories" / "daemons" / "sshd"),
        str(TESTS_PATH / "integration" / "factories" / "daemons" / "container"),
    )
    for item in items:
        skip_marker = pytest.mark.skip_on_salt_system_service(
            reason="There's no added value in running these tests against Salt intalled on the system."
        )
        if str(item.fspath).startswith(system_service_skip_paths):
            item.add_marker(skip_marker)
