# -*- coding: utf-8 -*-
"""
    tests.functional.test_sys_stats
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Tests related to processes system statistics enabled by the `--sys-stats` flag.
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

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
        import shutil

        from saltfactories.utils.processes.sshd import SshdDaemon


        @pytest.fixture(scope="module")
        def sshd_config_dir(salt_factories):
            config_dir = salt_factories.root_dir.join("sshd").ensure(dir=True)
            yield config_dir.strpath
            shutil.rmtree(config_dir.strpath, ignore_errors=True)


        @pytest.fixture(scope="module")
        def sshd(request, sshd_config_dir, salt_factories):
            return salt_factories.spawn_daemon(
                request, "sshd", SshdDaemon, "test-sshd", config_dir=sshd_config_dir, cwd=sshd_config_dir
            )

        def test_one(sshd):
            assert sshd.is_alive()
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
            "* sshd  -  CPU: * %   MEM: * % (RSS)",
            "* 1 passed in *",
        ]
    )
