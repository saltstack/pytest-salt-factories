# -*- coding: utf-8 -*-
"""
    saltfactories.utils.processes.salts
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Salt's related daemon classes and CLI processes implementations
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import sys

from saltfactories.utils.processes.bases import FactoryDaemonScriptBase
from saltfactories.utils.processes.bases import FactoryPythonScriptBase

log = logging.getLogger(__name__)


class SaltConfigMixin(object):
    @property
    def config_dir(self):
        if "conf_file" in self.config:
            return os.path.dirname(self.config["conf_file"])

    @property
    def config_file(self):
        if "conf_file" in self.config:
            return self.config["conf_file"]

    def __repr__(self):
        return "<{} id='{id}' role='{__role}'>".format(self.__class__.__name__, **self.config)


class SaltScriptBase(FactoryPythonScriptBase, SaltConfigMixin):
    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None) or {}
        hard_crash = kwargs.pop("salt_hard_crash", False)
        super(SaltScriptBase, self).__init__(*args, **kwargs)
        self.config = config
        self.hard_crash = hard_crash

    def get_base_script_args(self):
        script_args = super(SaltScriptBase, self).get_base_script_args()
        config_dir = self.config_dir
        if config_dir:
            script_args.append("--config-dir={}".format(config_dir))
        script_args.append("--log-level=quiet")
        script_args.append("--out=json")
        return script_args

    def get_script_args(self):
        """
        Returns any additional arguments to pass to the CLI script
        """
        if not self.hard_crash:
            return super(SaltScriptBase, self).get_script_args()
        return ["--hard-crash"]

    def get_minion_tgt(self, kwargs):
        minion_tgt = None
        if "minion_tgt" in kwargs:
            minion_tgt = kwargs.pop("minion_tgt")
        return minion_tgt

    def build_cmdline(self, *args, **kwargs):  # pylint: disable=arguments-differ
        log.debug("Building cmdline. Input args: %s; Input kwargs: %s;", args, kwargs)
        minion_tgt = self._minion_tgt = self.get_minion_tgt(kwargs)
        proc_args = []
        if minion_tgt:
            proc_args.append(minion_tgt)
        # Double dash flags should always come first. Users should be doing this already when calling run()
        # but we just double check
        proc_args += sorted(args, key=lambda x: -1 if x.startswith("--") else 1)
        for key in kwargs:
            proc_args.append("{}={}".format(key, kwargs[key]))
        proc_args = super(SaltScriptBase, self).build_cmdline(*proc_args)
        log.debug("Built cmdline: %s", proc_args)
        return proc_args


class SaltDaemonScriptBase(FactoryDaemonScriptBase, FactoryPythonScriptBase, SaltConfigMixin):
    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None) or {}
        super(SaltDaemonScriptBase, self).__init__(*args, **kwargs)
        self.config = config

    def get_base_script_args(self):
        script_args = super(SaltDaemonScriptBase, self).get_base_script_args()
        config_dir = self.config_dir
        if config_dir:
            script_args.append("--config-dir={}".format(config_dir))
        script_args.append("--log-level=quiet")
        return script_args

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        raise NotImplementedError

    def get_log_prefix(self):
        """
        Returns the log prefix that shall be used for a salt daemon forwarding log records.
        It is also used by :py:func:`start_daemon` when starting the daemon subprocess.
        """
        try:
            return self._log_prefix
        except AttributeError:
            try:
                pytest_config_key = "pytest-{}".format(self.config["__role"])
                log_prefix = (
                    self.config.get(pytest_config_key, {}).get("log", {}).get("prefix") or ""
                )
                if log_prefix:
                    self._log_prefix = "[{}] ".format(log_prefix)
            except KeyError:
                # This should really be a salt daemon which always set's `__role` in its config
                self._log_prefix = super(SaltDaemonScriptBase, self).get_log_prefix()
        return self._log_prefix

    def get_display_name(self):
        """
        Returns a name to show when process stats reports are enabled
        """
        try:
            return self._display_name
        except AttributeError:
            self._display_name = self.get_log_prefix().strip().lstrip("[").rstrip("]")
        return self._display_name


class SaltMaster(SaltDaemonScriptBase):
    """
    Simple subclass to define a salt master daemon
    """

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        yield self.config["id"], "salt/master/{id}/start".format(**self.config)


class SaltMinion(SaltDaemonScriptBase):
    """
    Simple subclass to define a salt minion daemon
    """

    def get_base_script_args(self):
        script_args = super(SaltMinion, self).get_base_script_args()
        if sys.platform.startswith("win") is False:
            script_args.append("--disable-keepalive")
        return script_args

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        pytest_config = self.config["pytest-{}".format(self.config["__role"])]
        yield pytest_config["master_config"]["id"], "salt/{__role}/{id}/start".format(**self.config)


class SaltSyndic(SaltDaemonScriptBase):
    """
    Simple subclass to define a salt minion daemon
    """

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        pytest_config = self.config["pytest-{}".format(self.config["__role"])]
        yield pytest_config["master_config"]["id"], "salt/{__role}/{id}/start".format(**self.config)


class SaltProxyMinion(SaltDaemonScriptBase):
    """
    Simple subclass to define a salt proxy minion daemon
    """

    def get_base_script_args(self):
        script_args = super(SaltProxyMinion, self).get_base_script_args()
        if sys.platform.startswith("win") is False:
            script_args.append("--disable-keepalive")
        script_args.extend(["--proxyid", self.config["id"]])
        return script_args

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        pytest_config = self.config["pytest-{}".format(self.config["__role"])]
        yield pytest_config["master_config"]["id"], "salt/{__role}/{id}/start".format(**self.config)


class SaltCLI(SaltScriptBase):
    """
    Simple subclass to the salt CLI script
    """

    def process_output(self, stdout, stderr, cli_cmd=None):
        if "No minions matched the target. No command was sent, no jid was assigned.\n" in stdout:
            stdout = stdout.split("\n", 1)[1:][0]
        old_stdout = None
        if "--show-jid" in cli_cmd and stdout.startswith("jid: "):
            old_stdout = stdout
            stdout = stdout.split("\n", 1)[-1].strip()
        stdout, stderr, json_out = SaltScriptBase.process_output(self, stdout, stderr, cli_cmd)
        if old_stdout is not None:
            stdout = old_stdout
        if json_out:
            if not isinstance(json_out, dict):
                # A string was most likely loaded, not what we want.
                return stdout, stderr, None
            try:
                return stdout, stderr, json_out[self._minion_tgt]
            except KeyError:
                return stdout, stderr, json_out
        return stdout, stderr, json_out


class SaltCallCLI(SaltScriptBase):
    """
    Simple subclass to the salt-call CLI script
    """

    def get_minion_tgt(self, kwargs):
        return None

    def process_output(self, stdout, stderr, cli_cmd=None):
        # Under salt-call, the minion target is always "local"
        self._minion_tgt = "local"
        stdout, stderr, json_out = SaltScriptBase.process_output(self, stdout, stderr, cli_cmd)
        if json_out:
            if not isinstance(json_out, dict):
                # A string was most likely loaded, not what we want.
                return stdout, stderr, None
            try:
                return stdout, stderr, json_out[self._minion_tgt]
            except KeyError:
                return stdout, stderr, json_out
        return stdout, stderr, json_out


class SaltRunCLI(SaltScriptBase):
    """
    Simple subclass to the salt-run CLI script
    """

    def get_minion_tgt(self, kwargs):
        return None


class SaltCpCLI(SaltScriptBase):
    """
    Simple subclass to the salt-cp CLI script
    """

    def process_output(self, stdout, stderr, cli_cmd=None):
        if "No minions matched the target. No command was sent, no jid was assigned.\n" in stdout:
            stdout = stdout.split("\n", 1)[1:][0]
        stdout, stderr, json_out = SaltScriptBase.process_output(self, stdout, stderr, cli_cmd)
        if json_out:
            if not isinstance(json_out, dict):
                # A string was most likely loaded, not what we want.
                return stdout, stderr, None
            try:
                return stdout, stderr, json_out[self._minion_tgt]
            except KeyError:
                return stdout, stderr, json_out
        return stdout, stderr, json_out


class SaltKeyCLI(SaltScriptBase):
    """
    Simple subclass to the salt-key CLI script
    """

    def get_base_script_args(self):
        script_args = super(SaltKeyCLI, self).get_base_script_args()
        # As of Neon, salt-key still does not support --log-level
        # Only when we get the new logging merged in will we get that, so remove that CLI flag
        for idx, flag in enumerate(script_args):
            if flag.startswith("--log-level="):
                script_args.pop(idx)
                break
        return script_args

    def get_minion_tgt(self, kwargs):
        return None
