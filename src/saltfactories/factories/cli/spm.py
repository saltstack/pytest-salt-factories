"""
saltfactories.factories.cli.spm
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``spm`` CLI factory
"""
import attr

from saltfactories.factories.base import SaltCliFactory


@attr.s(kw_only=True, slots=True)
class SpmCliFactory(SaltCliFactory):
    """
    ``spm`` CLI factory
    """

    __cli_output_supported__ = attr.ib(repr=False, init=False, default=False)

    def get_minion_tgt(self, minion_tgt=None):
        return None
