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
def test_python_executable_fixture(pytester, python_executable):
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
