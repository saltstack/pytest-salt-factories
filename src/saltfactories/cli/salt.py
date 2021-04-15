"""
``salt`` CLI factory
"""
import attr
import pytest

from saltfactories.bases import SaltCli


@attr.s(kw_only=True, slots=True)
class Salt(SaltCli):
    """
    salt CLI factory
    """

    __cli_timeout_supported__ = attr.ib(repr=False, init=False, default=True)

    def cmdline(self, *args, minion_tgt=None, **kwargs):  # pylint: disable=arguments-differ
        skip_raise_exception_args = {"-V", "--version", "--versions-report", "--help"}
        if minion_tgt is None and not set(args).intersection(skip_raise_exception_args):
            raise pytest.UsageError(
                "The `minion_tgt` keyword argument is mandatory for the salt CLI factory"
            )
        return super().cmdline(*args, minion_tgt=minion_tgt, **kwargs)

    def process_output(self, stdout, stderr, cmdline=None):
        if "No minions matched the target. No command was sent, no jid was assigned.\n" in stdout:
            stdout = stdout.split("\n", 1)[1:][0]
        if cmdline and "--show-jid" in cmdline and stdout.startswith("jid: "):
            stdout = stdout.split("\n", 1)[-1].strip()
        return super().process_output(stdout, stderr, cmdline=cmdline)
