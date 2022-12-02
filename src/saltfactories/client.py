"""
Salt Client in-process implementation.
"""
import logging
import re

import attr
import pytest


log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True)
class LocalClient:
    """
    Wrapper class around Salt's local client.
    """

    STATE_FUNCTION_RUNNING_RE = re.compile(
        r"""The function (?:"|')(?P<state_func>.*)(?:"|') is running as PID """
        r"(?P<pid>[\d]+) and was started at (?P<date>.*) with jid (?P<jid>[\d]+)"
    )

    master_config = attr.ib(repr=False)
    functions_known_to_return_none = attr.ib(repr=False)
    __client = attr.ib(init=False, repr=False)

    @functions_known_to_return_none.default
    def _set_functions_known_to_return_none(self):
        return (
            "data.get",
            "file.chown",
            "file.chgrp",
            "pkg.refresh_db",
            "ssh.recv_known_host_entries",
            "time.sleep",
        )

    @__client.default
    def _set_client(self):
        import salt.client

        return salt.client.get_local_client(mopts=self.master_config)

    def run(self, function, *args, minion_tgt="minion", timeout=300, **kwargs):
        """
        Run a single salt function.

        Additional condition the return down to match the behavior of the raw function call.
        """
        if "f_arg" in kwargs:
            kwargs["arg"] = kwargs.pop("f_arg")
        if "f_timeout" in kwargs:
            kwargs["timeout"] = kwargs.pop("f_timeout")
        ret = self.__client.cmd(minion_tgt, function, args, timeout=timeout, kwarg=kwargs)
        if minion_tgt not in ret:
            pytest.fail(
                "WARNING(SHOULD NOT HAPPEN #1935): Failed to get a reply "
                "from the minion '{}'. Command output: {}".format(minion_tgt, ret)
            )
        elif ret[minion_tgt] is None and function not in self.functions_known_to_return_none:
            pytest.fail(
                "WARNING(SHOULD NOT HAPPEN #1935): Failed to get '{}' from "
                "the minion '{}'. Command output: {}".format(function, minion_tgt, ret)
            )

        # Try to match stalled state functions
        ret[minion_tgt] = self._check_state_return(ret[minion_tgt])

        return ret[minion_tgt]

    def _check_state_return(self, ret):
        if isinstance(ret, dict):
            # This is the supposed return format for state calls
            return ret

        if isinstance(ret, list):
            jids = []
            # These are usually errors
            for item in ret[:]:
                if not isinstance(item, str):
                    # We don't know how to handle this
                    continue
                match = self.STATE_FUNCTION_RUNNING_RE.match(item)
                if not match:
                    # We don't know how to handle this
                    continue
                jid = match.group("jid")
                if jid in jids:
                    continue

                jids.append(jid)
                job_data = self.run("saltutil.find_job", jid)
                job_kill = self.run("saltutil.kill_job", jid)

                msg = (
                    "A running state.single was found causing a state lock. "
                    "Job details: '{}'  Killing Job Returned: '{}'".format(job_data, job_kill)
                )
                ret.append("[TEST SUITE ENFORCED]{}[/TEST SUITE ENFORCED]".format(msg))
        return ret
