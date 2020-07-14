# -*- coding: utf-8 -*-
"""
    saltfactories.utils.processes.sshd
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    SSHD daemon process implementation
"""
import logging

from saltfactories.exceptions import ProcessFailed
from saltfactories.utils import ports
from saltfactories.utils.processes.bases import FactoryDaemonScriptBase
from saltfactories.utils.processes.bases import Popen

log = logging.getLogger(__name__)


class SshdDaemon(FactoryDaemonScriptBase):
    def __init__(self, *args, **kwargs):
        config_dir = kwargs.pop("config_dir")
        serve_port = kwargs.pop("serve_port", None)
        sshd_config_dict = kwargs.pop("sshd_config_dict", None) or {}
        super().__init__(*args, **kwargs)
        self.config_dir = config_dir
        self.serve_port = serve_port or ports.get_unused_localhost_port()
        _default_config = {
            "Port": self.serve_port,
            "ListenAddress": "127.0.0.1",
            "PermitRootLogin": "no",
            "ChallengeResponseAuthentication": "no",
            "PasswordAuthentication": "no",
            "PubkeyAuthentication": "yes",
            "PrintMotd": "no",
            "PidFile": self.config_dir / "sshd.pid",
        }
        _default_config.update(sshd_config_dict)
        self._sshd_config = _default_config
        self._write_config()

    def get_base_script_args(self):
        """
        Returns any additional arguments to pass to the CLI script
        """
        return ["-D", "-e", "-f", str(self.config_dir / "sshd_config")]

    def get_check_ports(self):
        """
        Return a list of ports to check against to ensure the daemon is running
        """
        return [self.serve_port]

    def _write_config(self):
        sshd_config_file = self.config_dir / "sshd_config"
        if not sshd_config_file.exists():
            # Let's generat the host keys
            host_keys = []
            for key_type in ("dsa", "rsa"):
                key_path = self.config_dir / "ssh_host_{}_key".format(key_type)
                if not key_path.exists():
                    cmdline = ["ssh-keygen", "-f", str(key_path), "-N", "", "-t", key_type]
                    proc = Popen(cmdline)
                    stdout, stderr = proc.communicate()
                    if proc.returncode:
                        raise ProcessFailed(
                            "Failed to generate {} key.",
                            cmdline=cmdline,
                            stdout=stdout,
                            stderr=stderr,
                            exitcode=proc.returncode,
                        )
                key_path.chmod(0o0400)
                host_keys.append(key_path)

            # Let's write a default config file
            with open(str(sshd_config_file), "w") as wfh:
                config_lines = sorted(
                    "{} {}\n".format(key, value) for key, value in self._sshd_config.items()
                )
                wfh.write("".join(config_lines))
                for host_key in host_keys:
                    wfh.write("HostKey {}\n".format(host_key))
            sshd_config_file.chmod(0o0600)
            with open(str(sshd_config_file), "r") as wfh:
                log.debug(
                    "Wrote to configuration file %s. Configuration:\n%s",
                    sshd_config_file,
                    wfh.read(),
                )
