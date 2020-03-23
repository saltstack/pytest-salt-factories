# -*- coding: utf-8 -*-
"""
    saltfactories.utils.processes.sshd
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    SSHD daemon process implementation
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import textwrap

from saltfactories.exceptions import ProcessFailed
from saltfactories.utils import ports
from saltfactories.utils.processes.bases import FactoryDaemonScriptBase
from saltfactories.utils.processes.bases import Popen

log = logging.getLogger(__name__)


class SshdDaemon(FactoryDaemonScriptBase):
    def __init__(self, *args, **kwargs):
        config_dir = kwargs.pop("config_dir")
        serve_port = kwargs.pop("serve_port", None)
        super(SshdDaemon, self).__init__(*args, **kwargs)
        self.config_dir = config_dir
        self.serve_port = serve_port or ports.get_unused_localhost_port()
        self._write_default_config()

    def get_base_script_args(self):
        """
        Returns any additional arguments to pass to the CLI script
        """
        return ["-D", "-e", "-f", os.path.join(self.config_dir, "sshd_config")]

    def get_check_ports(self):
        """
        Return a list of ports to check against to ensure the daemon is running
        """
        return [self.serve_port]

    def _write_default_config(self):
        sshd_config_file = os.path.join(self.config_dir, "sshd_config")
        if not os.path.isfile(sshd_config_file):
            # Let's generat the host keys
            host_keys = []
            for key_type in ("dsa", "rsa"):
                key_path = os.path.join(self.config_dir, "ssh_host_{}_key".format(key_type))
                if not os.path.exists(key_path):
                    cmdline = ["ssh-keygen", "-f", key_path, "-N", "", "-t", key_type]
                    proc = Popen(cmdline)
                    stdout, stderr = proc.communicate()
                    if proc.returncode:
                        raise ProcessFailed(
                            "Failed to generate {} key.",
                            cmdline=cmdline,
                            stdout=stdout,
                            stderr=stderr,
                        )
                os.chmod(key_path, 0o0400)
                host_keys.append(key_path)

            # Let's write a default config file
            with open(sshd_config_file, "w") as wfh:
                wfh.write(
                    textwrap.dedent(
                        """\
                Port {}
                ListenAddress 127.0.0.1
                PermitRootLogin no
                ChallengeResponseAuthentication no
                PasswordAuthentication no
                PubkeyAuthentication yes
                PrintMotd no
                PidFile {}
                """.format(
                            self.serve_port, os.path.join(self.config_dir, "sshd.pid")
                        )
                    )
                )
                for host_key in host_keys:
                    wfh.write("HostKey {}\n".format(host_key))
            os.chmod(sshd_config_file, 0o0600)
            with open(sshd_config_file, "r") as wfh:
                log.debug(
                    "Wrote to configuration file %s. Configuration:\n%s",
                    sshd_config_file,
                    wfh.read(),
                )
