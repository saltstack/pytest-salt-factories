"""
``salt-key`` CLI factory.
"""
import re

import attr

from saltfactories.bases import SaltCli


@attr.s(kw_only=True, slots=True)
class SaltKey(SaltCli):
    """
    salt-key CLI factory.
    """

    _output_replace_re = attr.ib(
        init=False,
        repr=False,
        default=re.compile(r"((The following keys are going to be.*:|Key for minion.*)\n)"),
    )
    # As of Neon, salt-key still does not support --log-level
    # Only when we get the new logging merged in will we get that, so remove that CLI flag
    __cli_log_level_supported__ = attr.ib(repr=False, init=False)

    @__cli_log_level_supported__.default
    def _default___cli_log_level_supported__(self):
        from salt.utils.parsers import SaltKeyOptionParser

        try:
            return SaltKeyOptionParser._skip_console_logging_config_ is False
        except AttributeError:  # pragma: no cover
            # New logging is in place
            try:
                return "--log-level" in SaltKeyOptionParser._console_log_level_cli_flags
            except AttributeError:
                return True

    def get_minion_tgt(self, minion_tgt=None):
        """
        Overridden method because salt-key does not target minions.
        """
        return None

    def process_output(self, stdout, stderr, cmdline=None):
        """
        Process the returned output.
        """
        # salt-key print()s to stdout regardless of output chosen
        stdout = self._output_replace_re.sub("", stdout)
        return super().process_output(stdout, stderr, cmdline=cmdline)
