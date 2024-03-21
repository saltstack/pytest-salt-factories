"""
Salt Factories PyTest plugin interface.
"""
import logging

import pytest

import saltfactories.utils.tempfiles

log = logging.getLogger(__name__)


def pytest_runtest_logstart(nodeid):
    """
    Signal the start of running a single test item.

    This hook will be called **before** :func:`pytest_runtest_setup`, :func:`pytest_runtest_call` and
    :func:`pytest_runtest_teardown` hooks.

    :param str nodeid: full id of the item
    :param location: a triple of ``(filename, linenum, testname)``
    """
    log.debug(">>>>>>> START %s >>>>>>>", nodeid)


def pytest_runtest_logfinish(nodeid):
    """
    Signal the complete finish of running a single test item.

    This hook will be called **after** :func:`pytest_runtest_setup`, :func:`pytest_runtest_call` and
    :func:`pytest_runtest_teardown` hooks.

    :param str nodeid: full id of the item
    :param location: a triple of ``(filename, linenum, testname)``
    """
    log.debug("<<<<<<< END %s <<<<<<<", nodeid)


def pytest_runtest_logreport(report):
    """
    Log the test running.

    Process the :py:class:`_pytest.reports.TestReport` produced for each
    of the setup, call and teardown runtest phases of an item.
    See :func:`pytest_runtest_protocol` for a description of the runtest protocol.
    """
    if report.when == "call":
        log.debug("======= %s %s ========", report.outcome.upper(), report.nodeid)


@pytest.hookimpl(trylast=True)
def pytest_load_initial_conftests(*_):
    """
    Register our pytest helpers.
    """
    # Do not move these deferred imports. It allows running against a Salt
    # onedir build in salt's repo checkout.
    import salt.version  # pylint: disable=import-outside-toplevel

    if salt.version.__saltstack_version__ < "3005":
        msg = f"Only salt>=3005 is supported(Installed version {salt.version.__saltstack_version__}"
        raise pytest.UsageError(msg)
    # pylint: disable=no-member
    if "temp_directory" not in pytest.helpers:
        pytest.helpers.register(saltfactories.utils.tempfiles.temp_directory, name="temp_directory")
    if "temp_file" not in pytest.helpers:
        pytest.helpers.register(saltfactories.utils.tempfiles.temp_file, name="temp_file")
    # pylint: enable=no-member
