"""
``salt-run`` CLI factory.
"""
import attr

from saltfactories.bases import SaltCli


@attr.s(kw_only=True, slots=True)
class SaltRun(SaltCli):
    """
    salt-run CLI factory.
    """

    __cli_timeout_supported__ = attr.ib(repr=False, init=False, default=True)

    def _get_default_timeout(self):
        return self.config.get("timeout")

    def get_minion_tgt(self, minion_tgt=None):
        """
        Overridden method because salt-run does not target minions.
        """
        return None

    def process_output(self, stdout, stderr, cmdline=None):
        """
        Process the returned output.
        """
        if "No minions matched the target. No command was sent, no jid was assigned.\n" in stdout:
            stdout = stdout.split("\n", 1)[1:][0]
        return super().process_output(stdout, stderr, cmdline=cmdline)
