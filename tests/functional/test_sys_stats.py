# -*- coding: utf-8 -*-
"""
    tests.functional.test_sys_stats
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Tests related to processes system statistics enabled by the `--sys-stats` flag.
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals


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
