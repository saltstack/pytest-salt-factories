import functools
import logging
import os
import pathlib
import stat
import tempfile
import textwrap

import _pytest._version
import pytest
import salt.version

log = logging.getLogger(__name__)

TESTS_PATH = pathlib.Path(__file__).resolve().parent
PYTEST_GE_7 = getattr(_pytest._version, "version_tuple", (-1, -1)) >= (7, 0)


try:  # pragma: no cover
    import importlib.metadata

    pkg_version = importlib.metadata.version
except ImportError:  # pragma: no cover
    try:
        import importlib_metadata

        pkg_version = importlib_metadata.version
    except ImportError:  # pragma: no cover
        import pkg_resources

        def pkg_version(package):
            return pkg_resources.get_distribution(package).version


def pkg_version_info(package):
    return tuple(int(part) for part in pkg_version(package).split(".") if part.isdigit())


if pkg_version_info("pytest") >= (6, 2):
    pytest_plugins = ["pytester"]
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
            st = os.stat(tfile.name)
            os.chmod(tfile.name, st.st_mode | stat.S_IEXEC)
        self.request.addfinalizer(functools.partial(self._delete_temp_file, tfile.name))
        with open(tfile.name) as rfh:
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
        with open(name, "w") as wfh:
            contents = textwrap.dedent(contents.lstrip("\n")).strip()
            wfh.write(contents)
        self.request.addfinalizer(functools.partial(self._delete_temp_file, name))
        with open(name) as rfh:
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


@pytest.mark.trylast
def pytest_configure(config):
    """
    Add our markers to PyTest.

    Called after command line options have been parsed
    and all plugins and initial conftest files been loaded.
    """
    # Expose the markers we use to pytest CLI
    config.addinivalue_line(
        "markers",
        "skip_on_salt_system_install: Marker to skip tests when testing"
        "against salt installed in the system.",
    )


@pytest.hookimpl(trylast=True)
def pytest_runtest_setup(item):
    salt_factories_fixture = item._request.getfixturevalue("salt_factories")
    if salt_factories_fixture.system_install is False:
        return
    exc_kwargs = {}
    if PYTEST_GE_7:
        exc_kwargs["_use_item_location"] = True
    system_install_skip_paths = (
        # There's no point on running these tests against a system install of salt
        str(TESTS_PATH / "unit"),
        str(TESTS_PATH / "functional"),
        str(TESTS_PATH / "scenarios" / "examples"),
        str(TESTS_PATH / "integration" / "factories" / "cli"),
        str(TESTS_PATH / "integration" / "factories" / "daemons" / "sshd"),
        str(TESTS_PATH / "integration" / "factories" / "daemons" / "container"),
    )
    if str(item.fspath).startswith(system_install_skip_paths):
        raise pytest.skip.Exception(
            "Test should not run against system install of Salt",
            **exc_kwargs,
        )

    skip_on_salt_system_install_marker = item.get_closest_marker("skip_on_salt_system_install")
    if skip_on_salt_system_install_marker is not None:
        raise pytest.skip.Exception(
            "Test should not run against system install of Salt",
            **exc_kwargs,
        )
