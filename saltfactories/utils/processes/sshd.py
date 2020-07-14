"""
    saltfactories.utils.processes.sshd
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    SSHD daemon process implementation
"""
import logging
import pathlib
import shutil
import subprocess

from saltfactories.exceptions import ProcessFailed
from saltfactories.utils import ports
from saltfactories.utils.processes.bases import FactoryDaemonScriptBase

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
            # Let's write a default config file
            config_lines = []
            for key, value in self._sshd_config.items():
                if isinstance(value, list):
                    for item in value:
                        config_lines.append("{} {}\n".format(key, item))
                    continue
                config_lines.append("{} {}\n".format(key, value))

            # Let's generat the host keys
            self._generate_dsa_key()
            self._generate_ecdsa_key()
            self._generate_ed25519_key()
            for host_key in pathlib.Path(self.config_dir.strpath).glob("ssh_host_*_key"):
                config_lines.append("HostKey {}\n".format(host_key))

            with open(str(sshd_config_file), "w") as wfh:
                wfh.write("".join(sorted(config_lines)))
            sshd_config_file.chmod(0o0600)
            with open(str(sshd_config_file)) as wfh:
                log.debug(
                    "Wrote to configuration file %s. Configuration:\n%s",
                    sshd_config_file,
                    wfh.read(),
                )

    def _generate_dsa_key(self):
        key_filename = "ssh_host_dsa_key"
        key_path_prv = self.config_dir / key_filename
        key_path_pub = self.config_dir / "{}.pub".format(key_filename)
        if key_path_prv.exists() and key_path_pub.exists():
            return
        self._ssh_keygen(key_filename, "dsa", "1024")
        for key_path in (key_path_prv, key_path_pub):
            key_path.chmod(0o0400)

    def _generate_ecdsa_key(self):
        key_filename = "ssh_host_ecdsa_key"
        key_path_prv = self.config_dir / key_filename
        key_path_pub = self.config_dir / "{}.pub".format(key_filename)
        if key_path_prv.exists() and key_path_pub.exists():
            return
        self._ssh_keygen(key_filename, "ecdsa", "521")
        for key_path in (key_path_prv, key_path_pub):
            key_path.chmod(0o0400)

    def _generate_ed25519_key(self):
        key_filename = "ssh_host_ed25519_key"
        key_path_prv = self.config_dir / key_filename
        key_path_pub = self.config_dir / "{}.pub".format(key_filename)
        if key_path_prv.exists() and key_path_pub.exists():
            return
        self._ssh_keygen(key_filename, "ed25519", "521")
        for key_path in (key_path_prv, key_path_pub):
            key_path.chmod(0o0400)

    def _ssh_keygen(self, key_filename, key_type, bits, comment=None):
        try:
            ssh_keygen = self._ssh_keygen_path
        except AttributeError:
            ssh_keygen = self._ssh_keygen_path = shutil.which("ssh-keygen")

        if comment is None:
            comment = '"$(whoami)@$(hostname)-$(date -I)"'

        cmdline = [
            ssh_keygen,
            "-t",
            key_type,
            "-b",
            bits,
            "-C",
            comment,
            "-f",
            key_filename,
            "-P",
            "",
        ]
        try:
            subprocess.run(
                cmdline,
                cwd=str(self.config_dir),
                check=True,
                universal_newlines=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as exc:
            raise ProcessFailed(
                "Failed to generate ssh key.",
                cmdline=exc.args,
                stdout=exc.stdout,
                stderr=exc.stderr,
                exitcode=exc.returncode,
            )
