"""
``salt-ssh`` CLI factory.
"""
import attr

from saltfactories.bases import SaltCli


@attr.s(kw_only=True, slots=True)
class SaltSsh(SaltCli):
    """
    salt CLI factory.
    """

    roster_file = attr.ib(default=None)
    client_key = attr.ib(default=None)
    target_host = attr.ib(default=None)
    ssh_user = attr.ib(default=None)

    def __attrs_post_init__(self):
        """
        Post attrs initialization routines.
        """
        super().__attrs_post_init__()
        if self.target_host is None:
            self.target_host = "127.0.0.1"

    def get_script_args(self):
        """
        Return the CLI arguments for the script.
        """
        script_args = super().get_script_args()
        if self.roster_file:
            script_args.append("--roster-file={}".format(self.roster_file))
        if self.client_key:
            script_args.append("--priv={}".format(self.client_key))
        if self.ssh_user:
            script_args.append("--user={}".format(self.ssh_user))
        return script_args

    def get_minion_tgt(self, minion_tgt=None):
        """
        Return the minion ID to target.
        """
        if minion_tgt is None and self.target_host:
            minion_tgt = self.target_host
        return minion_tgt
