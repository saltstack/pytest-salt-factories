"""
``spm`` CLI factory.
"""
import attr

from saltfactories.bases import SaltCli


@attr.s(kw_only=True, slots=True)
class Spm(SaltCli):
    """
    ``spm`` CLI factory.
    """

    __cli_output_supported__ = attr.ib(repr=False, init=False, default=False)

    def get_minion_tgt(self, minion_tgt=None):
        """
        Overridden method because spm does not target minions.
        """
        return None
