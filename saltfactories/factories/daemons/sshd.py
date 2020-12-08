"""
saltfactories.factories.daemons.sshd
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

SSHD daemon factory implementation
"""
import logging
import pathlib
import shutil
import subprocess
from datetime import datetime

import attr

from saltfactories.exceptions import FactoryFailure
from saltfactories.factories.base import DaemonFactory
from saltfactories.utils import ports
from saltfactories.utils import running_username
from saltfactories.utils import socket

log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True)
class SshdDaemonFactory(DaemonFactory):
    config_dir = attr.ib()
    listen_address = attr.ib(default=None)
    listen_port = attr.ib(default=None)
    authorized_keys = attr.ib(default=None)
    sshd_config_dict = attr.ib(default=None, repr=False)
    client_key = attr.ib(default=None, init=False, repr=False)
    sshd_config = attr.ib(default=None, init=False)

    def __attrs_post_init__(self):
        if self.authorized_keys is None:
            self.authorized_keys = []
        if self.sshd_config_dict is None:
            self.sshd_config_dict = {}
        if self.listen_address is None:
            self.listen_address = "127.0.0.1"
        if self.listen_port is None:
            self.listen_port = ports.get_unused_localhost_port()
        self.check_ports = [self.listen_port]
        if isinstance(self.config_dir, str):
            self.config_dir = pathlib.Path(self.config_dir)
        elif not isinstance(self.config_dir, pathlib.Path):
            # A py local path?
            self.config_dir = pathlib.Path(self.config_dir.strpath)
        self.config_dir.chmod(0o0700)
        authorized_keys_file = self.config_dir / "authorized_keys"

        # Let's generate the client key
        self.client_key = self._generate_client_ecdsa_key()
        with open("{}.pub".format(self.client_key)) as rfh:
            pubkey = rfh.read().strip()
            log.debug("SSH client pub key: %r", pubkey)
            self.authorized_keys.append(pubkey)

        # Write the authorized pub keys to file
        with open(str(authorized_keys_file), "w") as wfh:
            wfh.write("\n".join(self.authorized_keys))

        authorized_keys_file.chmod(0o0600)

        with open(str(authorized_keys_file)) as rfh:
            log.debug("AuthorizedKeysFile contents:\n%s", rfh.read())

        _default_config = {
            "ListenAddress": self.listen_address,
            "PermitRootLogin": "yes" if running_username() == "root" else "no",
            "ChallengeResponseAuthentication": "no",
            "PasswordAuthentication": "no",
            "PubkeyAuthentication": "yes",
            "PrintMotd": "no",
            "PidFile": self.config_dir / "sshd.pid",
            "AuthorizedKeysFile": authorized_keys_file,
        }
        if self.sshd_config_dict:
            _default_config.update(self.sshd_config_dict)
        self.sshd_config = _default_config
        self._write_config()
        super().__attrs_post_init__()

    def get_base_script_args(self):
        """
        Returns any additional arguments to pass to the CLI script
        """
        return ["-D", "-e", "-f", str(self.config_dir / "sshd_config"), "-p", str(self.listen_port)]

    def _write_config(self):
        sshd_config_file = self.config_dir / "sshd_config"
        if not sshd_config_file.exists():
            # Let's write a default config file
            config_lines = []
            for key, value in self.sshd_config.items():
                if isinstance(value, list):
                    for item in value:
                        config_lines.append("{} {}\n".format(key, item))
                    continue
                config_lines.append("{} {}\n".format(key, value))

            # Let's generate the host keys
            self._generate_server_dsa_key()
            self._generate_server_ecdsa_key()
            self._generate_server_ed25519_key()
            for host_key in pathlib.Path(self.config_dir).glob("ssh_host_*_key"):
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

    def _generate_client_ecdsa_key(self):
        key_filename = "client_key"
        key_path_prv = self.config_dir / key_filename
        key_path_pub = self.config_dir / "{}.pub".format(key_filename)
        if key_path_prv.exists() and key_path_pub.exists():
            return key_path_prv
        self._ssh_keygen(key_filename, "ecdsa", "521")
        for key_path in (key_path_prv, key_path_pub):
            key_path.chmod(0o0400)
        return key_path_prv

    def _generate_server_dsa_key(self):
        key_filename = "ssh_host_dsa_key"
        key_path_prv = self.config_dir / key_filename
        key_path_pub = self.config_dir / "{}.pub".format(key_filename)
        if key_path_prv.exists() and key_path_pub.exists():
            return key_path_prv
        self._ssh_keygen(key_filename, "dsa", "1024")
        for key_path in (key_path_prv, key_path_pub):
            key_path.chmod(0o0400)
        return key_path_prv

    def _generate_server_ecdsa_key(self):
        key_filename = "ssh_host_ecdsa_key"
        key_path_prv = self.config_dir / key_filename
        key_path_pub = self.config_dir / "{}.pub".format(key_filename)
        if key_path_prv.exists() and key_path_pub.exists():
            return key_path_prv
        self._ssh_keygen(key_filename, "ecdsa", "521")
        for key_path in (key_path_prv, key_path_pub):
            key_path.chmod(0o0400)
        return key_path_prv

    def _generate_server_ed25519_key(self):
        key_filename = "ssh_host_ed25519_key"
        key_path_prv = self.config_dir / key_filename
        key_path_pub = self.config_dir / "{}.pub".format(key_filename)
        if key_path_prv.exists() and key_path_pub.exists():
            return key_path_prv
        self._ssh_keygen(key_filename, "ed25519", "521")
        for key_path in (key_path_prv, key_path_pub):
            key_path.chmod(0o0400)
        return key_path_prv

    def _ssh_keygen(self, key_filename, key_type, bits, comment=None):
        try:
            ssh_keygen = self._ssh_keygen_path
        except AttributeError:
            ssh_keygen = self._ssh_keygen_path = shutil.which("ssh-keygen")

        if comment is None:
            comment = "{user}@{host}-{date}".format(
                user=running_username(),
                host=socket.gethostname(),
                date=datetime.utcnow().strftime("%Y-%m-%d"),
            )

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
            raise FactoryFailure(
                "Failed to generate ssh key.",
                cmdline=exc.args,
                stdout=exc.stdout,
                stderr=exc.stderr,
                exitcode=exc.returncode,
            )
