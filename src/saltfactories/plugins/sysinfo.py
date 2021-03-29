"""
..
    PYTEST_DONT_REWRITE


    saltfactories.plugins.sysinfo
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    System Information Plugin
"""
import io
import pathlib
import tempfile

import pytest
import salt.config
import salt.loader
import salt.utils.yaml
import salt.version


def pytest_addoption(parser):
    """
    register argparse-style options and ini-style config values.
    """
    output_options_group = parser.getgroup("Output Options")
    output_options_group.addoption(
        "--sys-info",
        "--sysinfo",
        default=False,
        action="store_true",
        help="Print system information on test session startup",
    )


@pytest.hookimpl(hookwrapper=True, trylast=True)
def pytest_sessionstart(session):
    """called after the ``Session`` object has been created and before performing collection
    and entering the run test loop.

    :param _pytest.main.Session session: the pytest session object
    """
    # Let PyTest do its own thing
    yield
    if session.config.getoption("--sys-info") is True:
        # And now we add our reporting sections
        terminal_reporter = session.config.pluginmanager.getplugin("terminalreporter")
        terminal_reporter.ensure_newline()
        terminal_reporter.section("System Information", sep=">")
        terminal_reporter.section("Salt Versions Report", sep="-", bold=True)
        terminal_reporter.write(
            "\n".join(
                "  {}".format(line.rstrip()) for line in salt.version.versions_report()
            ).rstrip()
            + "\n"
        )
        terminal_reporter.ensure_newline()
        # System Grains
        root_dir = pathlib.Path(tempfile.mkdtemp())
        conf_file = root_dir / "conf" / "minion"
        conf_file.parent.mkdir()
        minion_config_defaults = salt.config.DEFAULT_MINION_OPTS.copy()
        minion_config_defaults.update(
            {
                "id": "saltfactories-reports-minion",
                "root_dir": str(root_dir),
                "conf_file": str(conf_file),
                "cachedir": "cache",
                "pki_dir": "pki",
                "file_client": "local",
                "server_id_use_crc": "adler32",
            }
        )
        minion_config = salt.config.minion_config(None, defaults=minion_config_defaults)
        grains = salt.loader.grains(minion_config)
        grains_output_file = io.StringIO()
        salt.utils.yaml.safe_dump(grains, grains_output_file, default_flow_style=False)
        grains_output_file.seek(0)
        terminal_reporter.section("System Grains Report", sep="-")
        terminal_reporter.write(
            "\n".join(
                "  {}".format(line.rstrip()) for line in grains_output_file.read().splitlines()
            ).rstrip()
            + "\n"
        )
        terminal_reporter.ensure_newline()
        terminal_reporter.section("System Information", sep="<")
        terminal_reporter.ensure_newline()
