"""
    tests.functional.test_sys_stats
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Tests related to processes system statistics enabled by the `--sys-stats` flag.
"""
import pytest


def test_basic_sys_stats(testdir):
    p = testdir.makepyfile(
        """
        def test_one():
            assert True
        """
    )
    res = testdir.runpytest("-vv", "--sys-stats")
    res.assert_outcomes(passed=1)
    res.stdout.fnmatch_lines(
        [
            "* PASSED*",
            "* Processes Statistics *",
            "* System  -  CPU: * %   MEM: * % (Virtual Memory)*",
            "* Test Suite Run  -  CPU: * %   MEM: * % (RSS)",
            "* 1 passed in *",
        ]
    )


def test_basic_sys_stats_uss(testdir):
    p = testdir.makepyfile(
        """
        def test_one():
            assert True
        """
    )
    res = testdir.runpytest("-vv", "--sys-stats", "--sys-stats-uss-mem")
    res.assert_outcomes(passed=1)
    res.stdout.fnmatch_lines(
        [
            "* PASSED*",
            "* Processes Statistics *",
            "* System  -  CPU: * %   MEM: * % (Virtual Memory)*",
            "* Test Suite Run  -  CPU: * %   MEM: * % (USS)",
            "* 1 passed in *",
        ]
    )


@pytest.mark.skip_on_windows
@pytest.mark.skip_if_binaries_missing("sshd", "ssh-keygen")
def test_proc_sys_stats(testdir):
    p = testdir.makepyfile(
        """
        import pytest

        @pytest.fixture(scope="module")
        def sshd(request, salt_factories):
            factory = salt_factories.get_sshd_daemon("sshd")
            with factory.started():
                yield factory

        def test_one(sshd):
            assert sshd.is_running()
        """
    )
    res = testdir.runpytest("-vv", "--sys-stats")
    res.assert_outcomes(passed=1)
    res.stdout.fnmatch_lines(
        [
            "* PASSED*",
            "* Processes Statistics *",
            "* System  -  CPU: * %   MEM: * % (Virtual Memory)*",
            "* Test Suite Run  -  CPU: * %   MEM: * % (RSS) * CHILD PROCS: *",
            "* SSHD  -  CPU: * %   MEM: * % (RSS)*",
            "* 1 passed in *",
        ]
    )
