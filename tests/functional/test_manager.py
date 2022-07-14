"""
Test the salt factories manager.
"""
import sys

import pytest

pytestmark = [
    pytest.mark.skip_on_windows(reason="Windows backslashed mess it all up. Skipping for now."),
]


def _python_excutable_ids(value):
    return "python_executable={}".format(value or "sys.executable")


@pytest.mark.parametrize(
    "python_executable", ["/where/bin/python", None], ids=_python_excutable_ids
)
def test_python_executable_cli(pytester, python_executable):
    args = []
    if python_executable:
        args.append("--python-executable={}".format(python_executable))

    pytester.makepyfile(
        """
        def test_factories(salt_factories):
            assert salt_factories.python_executable == '{python_executable}'

        def test_master(salt_factories):
            factory = salt_factories.salt_master_daemon("foo-master")
            assert factory.python_executable == '{python_executable}'
        """.format(
            python_executable=python_executable or sys.executable
        )
    )

    res = pytester.runpytest_subprocess(*args)
    res.assert_outcomes(passed=2)


@pytest.mark.parametrize(
    "python_executable", ["/where/bin/python", None], ids=_python_excutable_ids
)
def test_python_executable_config_fixture(pytester, python_executable):
    pytester.makepyfile(
        """
        def test_factories(salt_factories):
            assert salt_factories.python_executable == '{python_executable}'

        def test_master(salt_factories):
            factory = salt_factories.salt_master_daemon("foo-master")
            assert factory.python_executable == '{python_executable}'
        """.format(
            python_executable=python_executable or sys.executable
        )
    )
    pytester.makeconftest(
        """
        import pytest

        @pytest.fixture(scope="session")
        def salt_factories_config():
            return {{
                "python_executable": {!r}
            }}
        """.format(
            python_executable
        )
    )
    res = pytester.runpytest_subprocess()
    res.assert_outcomes(passed=2)


@pytest.fixture
def scripts_dir(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for fname in ("salt-master", "salt-minion"):
        bin_dir.joinpath(fname).touch()
    return bin_dir


def test_scripts_dir_cli(pytester, scripts_dir):
    pytester.makeconftest(
        """
        import pytest

        @pytest.fixture(scope="session")
        def salt_factories_config():
            return {{
                "python_executable": {!r}
            }}
        """.format(
            sys.executable
        )
    )
    pytester.makepyfile(
        """
        def test_factories(salt_factories):
            assert str(salt_factories.scripts_dir) == r'{}'

        def test_python_executable(salt_factories):
            assert salt_factories.python_executable is None

        def test_master(salt_factories):
            factory = salt_factories.salt_master_daemon("foo-master")
            assert str(factory.script_name) == r'{}'
        """.format(
            scripts_dir,
            scripts_dir / "salt-master",
        )
    )

    res = pytester.runpytest_subprocess("--scripts-dir={}".format(scripts_dir))
    res.assert_outcomes(passed=3)


def test_scripts_dir_config_fixture(pytester, scripts_dir):
    pytester.makeconftest(
        """
        import pytest

        @pytest.fixture(scope="session")
        def salt_factories_config():
            return {{
                "scripts_dir": r'{}',
                "python_executable": '{}',
            }}
        """.format(
            scripts_dir, sys.executable
        )
    )
    pytester.makepyfile(
        """
        def test_factories(salt_factories):
            assert str(salt_factories.scripts_dir) == r'{}'

        def test_python_executable(salt_factories):
            assert salt_factories.python_executable is None

        def test_master(salt_factories):
            factory = salt_factories.salt_master_daemon("foo-master")
            assert str(factory.script_name) == '{}'
        """.format(
            scripts_dir,
            scripts_dir / "salt-master",
        )
    )

    res = pytester.runpytest_subprocess()
    res.assert_outcomes(passed=3)


def _system_service_ids(value):
    return "system-service({})".format(value)


@pytest.mark.parametrize("system_service", [True, False], ids=_system_service_ids)
def test_system_service_cli(pytester, system_service, tmp_path):
    args = []
    if system_service:
        args.append("--system-service")

    pytester.makepyfile(
        """
        import pathlib

        def test_factories(salt_factories):
            assert salt_factories.system_service is {system_service}

        def test_master(salt_factories):
            # We set root_dir here to allow tests to run without being root
            salt_factories.root_dir = pathlib.Path('{root_dir}')

            factory = salt_factories.salt_master_daemon("foo-master")
            assert factory.system_service is {system_service}
            if {system_service}:
                assert "engines_dirs" in factory.config
                assert factory.config["engines_dirs"]
                assert "log_handlers_dirs" in factory.config
                assert factory.config["log_handlers_dirs"]
        """.format(
            root_dir=tmp_path,
            system_service=system_service,
        )
    )

    res = pytester.runpytest_subprocess(*args)
    res.assert_outcomes(passed=2)


@pytest.mark.parametrize("system_service", [True, False], ids=_system_service_ids)
def test_system_service_config_fixture(pytester, system_service, tmp_path):
    pytester.makeconftest(
        """
        import pytest

        @pytest.fixture(scope="session")
        def salt_factories_config():
            return {{
                "root_dir": r'{}',
                "system_service": {},
            }}
        """.format(
            tmp_path,
            system_service,
        )
    )
    args = []
    if system_service:
        args.append("--system-service")

    pytester.makepyfile(
        """
        import pathlib

        def test_root_dir(salt_factories):
            # The default root dir when system_service is True
            if {system_service}:
                assert str(salt_factories.root_dir) == '/'
            else:
                assert str(salt_factories.root_dir) == r'{root_dir}'

        def test_factories(salt_factories):
            assert salt_factories.system_service is {system_service}

        def test_master(salt_factories):
            if {system_service}:
                # We set root_dir here to allow tests to run without being root
                salt_factories.root_dir = pathlib.Path(r'{root_dir}')

            factory = salt_factories.salt_master_daemon("foo-master")
            assert factory.system_service is {system_service}
            if {system_service}:
                assert "engines_dirs" in factory.config
                assert factory.config["engines_dirs"]
                assert "log_handlers_dirs" in factory.config
                assert factory.config["log_handlers_dirs"]
        """.format(
            root_dir=tmp_path,
            system_service=system_service,
        )
    )

    res = pytester.runpytest_subprocess(*args)
    res.assert_outcomes(passed=3)
