# pylint: disable=wrong-spelling-in-docstring
"""
The system information plugin can be enabled by passing ``--sys-info`` to pytest.

When enabled it will include some output sections when starting pytest.
Here's an example of the output(partial, for brevity):

.. code-block:: console

   >>>>>>>>>>>>>>>>>>>>>>>>>>> System Information >>>>>>>>>>>>>>>>>>>>>>>>>>>
   -------------------------- Salt Versions Report --------------------------
     Salt Version:
               Salt: 3003

     Dependency Versions:
               cffi: Not Installed
           cherrypy: Not Installed
           dateutil: Not Installed
          docker-py: 5.0.0
              gitdb: Not Installed
          gitpython: Not Installed
             Jinja2: 3.0.1
            libgit2: Not Installed
           M2Crypto: Not Installed
               Mako: Not Installed
            msgpack: 1.0.2
       msgpack-pure: Not Installed
       mysql-python: Not Installed
          pycparser: Not Installed
           pycrypto: Not Installed
       pycryptodome: 3.10.1
             pygit2: Not Installed
             Python: 3.7.7 (default, Oct 24 2021, 07:30:53)
       python-gnupg: Not Installed
             PyYAML: 5.4.1
              PyZMQ: 22.1.0
              smmap: Not Installed
            timelib: Not Installed
            Tornado: 4.5.3
                ZMQ: 4.3.4

     System Versions:
               dist: arch rolling n/a
             locale: UTF-8
            machine: x86_64
            release: 5.16.2-arch1-1
             system: Linux
            version: Arch Linux rolling n/a
   -------------------------- System Grains Report --------------------------
     biosreleasedate: 12/06/2019
     biosversion: N1EET87W (1.60 )
     cpu_flags:
     - fpu
     - vme
     gpus:
      - model: HD Graphics 530
        vendor: intel
      - model: GM107GLM [Quadro M1000M]
        vendor: nvidia
     kernelrelease: 5.16.2-arch1-1
     kernelversion: '#1 SMP PREEMPT Thu, 20 Jan 2022 16:18:29 +0000'
     locale_info:
       defaultencoding: UTF-8
       defaultlanguage: pt_PT
       detectedencoding: UTF-8
       timezone: unknown
     mem_total: 64137
     num_cpus: 8
     num_gpus: 2
     os: Arch
     os_family: Arch
     osarch: x86_64
     oscodename: n/a
     osfinger: Arch-rolling
     osfullname: Arch
     osrelease: rolling
     virtual: physical
     zfs_feature_flags: false
     zfs_support: false
     zmqversion: 4.3.4
   <<<<<<<<<<<<<<<<<<<<<<<<<<< System Information <<<<<<<<<<<<<<<<<<<<<<<<<<<

..
    PYTEST_DONT_REWRITE
"""
# pylint: enable=wrong-spelling-in-docstring
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
    Register argparse-style options and ini-style config values.
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
    """
    Setup the plugin when the test session starts.

    Called after the ``Session`` object has been created and before performing collection
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
