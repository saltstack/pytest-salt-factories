"""
Test the salt factories manager.
"""
import sys

import pytest


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
            assert str(salt_factories.scripts_dir) == '{}'

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

    res = pytester.runpytest_subprocess("--scripts-dir={}".format(scripts_dir))
    res.assert_outcomes(passed=3)


def test_scripts_dir_config_fixture(pytester, scripts_dir):
    pytester.makeconftest(
        """
        import pytest

        @pytest.fixture(scope="session")
        def salt_factories_config():
            return {{
                "scripts_dir": '{}',
                "python_executable": '{}',
            }}
        """.format(
            scripts_dir, sys.executable
        )
    )
    pytester.makepyfile(
        """
        def test_factories(salt_factories):
            assert str(salt_factories.scripts_dir) == '{}'

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
