"""
saltfactories.factories.cli.salt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``salt`` CLI factory
"""
import attr

from saltfactories.factories.base import SaltCliFactory as _SaltCliFactory


@attr.s(kw_only=True, slots=True)
class SaltCliFactory(_SaltCliFactory):
    """
    salt CLI factory
    """

    __cli_timeout_supported__ = attr.ib(repr=False, init=False, default=True)

    def process_output(self, stdout, stderr, cmdline=None):
        if "No minions matched the target. No command was sent, no jid was assigned.\n" in stdout:
            stdout = stdout.split("\n", 1)[1:][0]
        old_stdout = None
        if cmdline and "--show-jid" in cmdline and stdout.startswith("jid: "):
            old_stdout = stdout
            stdout = stdout.split("\n", 1)[-1].strip()
        return super().process_output(stdout, stderr, cmdline=cmdline)
