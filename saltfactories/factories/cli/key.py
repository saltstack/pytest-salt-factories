"""
..
    PYTEST_DONT_REWRITE


saltfactories.factories.cli.key
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``salt-key`` CLI factory
"""
import re

import attr
from salt.utils.parsers import SaltKeyOptionParser

from saltfactories.factories.base import SaltCliFactory

try:
    SALT_KEY_LOG_LEVEL_SUPPORTED = SaltKeyOptionParser._skip_console_logging_config_ is False
except AttributeError:  # pragma: no cover
    # New logging is in place
    SALT_KEY_LOG_LEVEL_SUPPORTED = True


@attr.s(kw_only=True, slots=True)
class SaltKeyCliFactory(SaltCliFactory):
    """
    salt-key CLI factory
    """

    _output_replace_re = attr.ib(
        init=False,
        repr=False,
        default=re.compile(r"((The following keys are going to be.*:|Key for minion.*)\n)"),
    )
    # As of Neon, salt-key still does not support --log-level
    # Only when we get the new logging merged in will we get that, so remove that CLI flag
    __cli_log_level_supported__ = attr.ib(
        repr=False, init=False, default=SALT_KEY_LOG_LEVEL_SUPPORTED
    )

    def get_minion_tgt(self, minion_tgt=None):
        return None

    def process_output(self, stdout, stderr, cmdline=None):
        # salt-key print()s to stdout regardless of output chosen
        stdout = self._output_replace_re.sub("", stdout)
        return super().process_output(stdout, stderr, cmdline=cmdline)
