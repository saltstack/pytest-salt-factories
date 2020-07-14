"""
    saltfactories.plugins.sysstats
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Process stats PyTest plugin interface
"""
import os
from collections import OrderedDict

import psutil
import pytest

from saltfactories.utils.processes.stats import SaltTerminalReporter


def pytest_addoption(parser):
    """
    register argparse-style options and ini-style config values.
    """
    output_options_group = parser.getgroup("Output Options")
    output_options_group.addoption(
        "--sys-stats",
        default=False,
        action="store_true",
        help="Print System CPU and MEM statistics after each test execution.",
    )
    output_options_group.addoption(
        "--sys-stats-no-children",
        default=False,
        action="store_true",
        help="Don't include child processes memory statistics.",
    )
    output_options_group.addoption(
        "--sys-stats-uss-mem",
        default=False,
        action="store_true",
        help='Use the USS("Unique Set Size", memory unique to a process which would be freed if the process was '
        "terminated) memory instead which is more expensive to calculate.",
    )


def pytest_sessionstart(session):
    if session.config.getoption("--sys-stats") is True:
        stats_processes = OrderedDict((("Test Suite Run", psutil.Process(os.getpid())),))
    else:
        stats_processes = None
    session.stats_processes = stats_processes


@pytest.mark.trylast
def pytest_configure(config):
    """
    called after command line options have been parsed
    and all plugins and initial conftest files been loaded.
    """
    if config.getoption("--sys-stats") is True:
        # Register our terminal reporter
        if not getattr(config, "slaveinput", None):
            standard_reporter = config.pluginmanager.getplugin("terminalreporter")
            salt_reporter = SaltTerminalReporter(standard_reporter.config)

            config.pluginmanager.unregister(standard_reporter)
            config.pluginmanager.register(salt_reporter, "terminalreporter")
