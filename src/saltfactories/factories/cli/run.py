"""
saltfactories.factories.cli.run
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``salt-run`` CLI factory
"""
import attr

from saltfactories.factories.base import SaltCliFactory


@attr.s(kw_only=True, slots=True)
class SaltRunCliFactory(SaltCliFactory):
    """
    salt-run CLI factory
    """

    __cli_timeout_supported__ = attr.ib(repr=False, init=False, default=True)

    def get_minion_tgt(self, minion_tgt=None):
        return None

    def process_output(self, stdout, stderr, cmdline=None):
        if "No minions matched the target. No command was sent, no jid was assigned.\n" in stdout:
            stdout = stdout.split("\n", 1)[1:][0]
        return super().process_output(stdout, stderr, cmdline=cmdline)
