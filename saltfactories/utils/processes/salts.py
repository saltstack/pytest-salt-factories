# -*- coding: utf-8 -*-
"""
    saltfactories.utils.processes.salts
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Salt's related daemon classes and CLI processes implementations
"""
import json
import logging
import os
import re
import sys

import pytest

try:
    import salt.client
    from salt.utils.parsers import SaltKeyOptionParser

    try:
        SALT_KEY_LOG_LEVEL_SUPPORTED = SaltKeyOptionParser._skip_console_logging_config_ is False
    except AttributeError:
        # New logging is in place
        SALT_KEY_LOG_LEVEL_SUPPORTED = True
except ImportError:  # pragma: no cover
    # We need salt to test salt with saltfactories, and, when pytest is rewriting modules for proper assertion
    # reporting, we still haven't had a chance to inject the salt path into sys.modules, so we'll hit this
    # import error, but its safe to pass
    SALT_KEY_LOG_LEVEL_SUPPORTED = False

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

    __cli_timeout_supported__ = False
    __cli_log_level_supported__ = True

    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None) or {}
        hard_crash = kwargs.pop("salt_hard_crash", False)
        super().__init__(*args, **kwargs)
        self.config = config
        self.hard_crash = hard_crash

    def get_script_args(self):
        """
        Returns any additional arguments to pass to the CLI script
        """
        if not self.hard_crash:
            return super().get_script_args()
        return ["--hard-crash"]

    def get_minion_tgt(self, kwargs):
        minion_tgt = None
        if "minion_tgt" in kwargs:
            minion_tgt = kwargs.pop("minion_tgt")
        return minion_tgt

    def build_cmdline(self, *args, **kwargs):  # pylint: disable=arguments-differ
        log.debug("Building cmdline. Input args: %s; Input kwargs: %s;", args, kwargs)
        minion_tgt = self._minion_tgt = self.get_minion_tgt(kwargs)
        cmdline = []

        args = list(args)

        # Handle the config directory flag
        for arg in args:
            if arg.startswith("--config-dir="):
                break
            if arg in ("-c", "--config-dir"):
                break
        else:
            cmdline.append("--config-dir={}".format(self.config_dir))

        # Handle the timeout CLI flag, if supported
        if self.__cli_timeout_supported__:
            salt_cli_timeout_next = False
            for arg in args:
                if arg.startswith("--timeout="):
                    # Let's actually change the _terminal_timeout value which is used to
                    # calculate when the run() method should actually timeout
                    if self._terminal_timeout_set_explicitly is False:
                        salt_cli_timeout = arg.split("--timeout=")[-1]
                        try:
                            self._terminal_timeout = int(salt_cli_timeout) + 5
                        except ValueError:
                            # Not a number? Let salt do it's error handling
                            pass
                    break
                if salt_cli_timeout_next:
                    if self._terminal_timeout_set_explicitly is False:
                        try:
                            self._terminal_timeout = int(arg) + 5
                        except ValueError:
                            # Not a number? Let salt do it's error handling
                            pass
                    break
                if arg == "-t" or arg.startswith("--timeout"):
                    salt_cli_timeout_next = True
                    continue
            else:
                salt_cli_timeout = self._terminal_timeout
                if salt_cli_timeout and self._terminal_timeout_set_explicitly is False:
                    # Shave off a few seconds so that the salt command times out before the terminal does
                    salt_cli_timeout -= 5
                if salt_cli_timeout:
                    # If it's still a positive number, add it to the salt command CLI flags
                    cmdline.append("--timeout={}".format(salt_cli_timeout))

        # Handle the output flag
        for arg in args:
            if arg in ("--out", "--output"):
                break
            if arg.startswith(("--out=", "--output=")):
                break
        else:
            # No output was passed, the default output is JSON
            cmdline.append("--out=json")

        if self.__cli_log_level_supported__:
            # Handle the logging flag
            for arg in args:
                if arg in ("-l", "--log-level"):
                    break
                if arg.startswith("--log-level="):
                    break
            else:
                # Default to being quiet on console output
                cmdline.append("--log-level=quiet")

        if minion_tgt:
            cmdline.append(minion_tgt)

        # Add the remaning args
        cmdline.extend(args)

        for key in kwargs:
            value = kwargs[key]
            if not isinstance(value, str):
                value = json.dumps(value)
            cmdline.append("{}={}".format(key, value))
        cmdline = super().build_cmdline(*cmdline)
        log.debug("Built cmdline: %s", cmdline)
        return cmdline

    def process_output(self, stdout, stderr, cmdline=None):
        stdout, stderr, json_out = super().process_output(stdout, stderr, cmdline=cmdline)
        if json_out and isinstance(json_out, str) and "--out=json" in cmdline:
            # Sometimes the parsed JSON is just a string, for example:
            #  OUTPUT: '"The salt master could not be contacted. Is master running?"\n'
            #  LOADED JSON: 'The salt master could not be contacted. Is master running?'
            #
            # In this case, we assign the loaded JSON to stdout and reset json_out
            stdout = json_out
            json_out = None
        return stdout, stderr, json_out


class SaltDaemonScriptBase(FactoryDaemonScriptBase, FactoryPythonScriptBase, SaltConfigMixin):
    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None) or {}
        extra_checks_callback = kwargs.pop("extra_checks_callback", None)
        super().__init__(*args, **kwargs)
        self.config = config
        self.extra_checks_callback = extra_checks_callback

    def get_base_script_args(self):
        script_args = super().get_base_script_args()
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
                    self._log_prefix = "[{}] ".format(
                        log_prefix.format(cli_name=os.path.basename(self.cli_script_name))
                    )
            except KeyError:
                # This should really be a salt daemon which always set's `__role` in its config
                self._log_prefix = super().get_log_prefix()
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

    def run_extra_checks(self, salt_factories):
        """
        This extra check is here so that we confirm the daemon is up as soon as it get's responsive
        """
        if self.extra_checks_callback is None:
            return True
        return self.extra_checks_callback(salt_factories, self.config)


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
        script_args = super().get_base_script_args()
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

    def __init__(self, *args, **kwargs):
        include_proxyid_cli_flag = kwargs.pop("include_proxyid_cli_flag", True)
        super().__init__(*args, **kwargs)
        self.include_proxyid_cli_flag = include_proxyid_cli_flag

    def get_base_script_args(self):
        script_args = super().get_base_script_args()
        if sys.platform.startswith("win") is False:
            script_args.append("--disable-keepalive")
        if self.include_proxyid_cli_flag is True:
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

    __cli_timeout_supported__ = True

    def process_output(self, stdout, stderr, cmdline=None):
        if "No minions matched the target. No command was sent, no jid was assigned.\n" in stdout:
            stdout = stdout.split("\n", 1)[1:][0]
        old_stdout = None
        if "--show-jid" in cmdline and stdout.startswith("jid: "):
            old_stdout = stdout
            stdout = stdout.split("\n", 1)[-1].strip()
        stdout, stderr, json_out = SaltScriptBase.process_output(self, stdout, stderr, cmdline)
        if old_stdout is not None:
            stdout = old_stdout
        if json_out:
            try:
                return stdout, stderr, json_out[self._minion_tgt]
            except KeyError:
                return stdout, stderr, json_out
        return stdout, stderr, json_out


class SaltCallCLI(SaltScriptBase):
    """
    Simple subclass to the salt-call CLI script
    """

    __cli_timeout_supported__ = True

    def get_minion_tgt(self, kwargs):
        return None

    def process_output(self, stdout, stderr, cmdline=None):
        # Under salt-call, the minion target is always "local"
        self._minion_tgt = "local"
        stdout, stderr, json_out = SaltScriptBase.process_output(self, stdout, stderr, cmdline)
        if json_out:
            try:
                return stdout, stderr, json_out[self._minion_tgt]
            except KeyError:
                return stdout, stderr, json_out
        return stdout, stderr, json_out


class SaltRunCLI(SaltScriptBase):
    """
    Simple subclass to the salt-run CLI script
    """

    __cli_timeout_supported__ = True

    def get_minion_tgt(self, kwargs):
        return None

    def process_output(self, stdout, stderr, cmdline=None):
        if "No minions matched the target. No command was sent, no jid was assigned.\n" in stdout:
            stdout = stdout.split("\n", 1)[1:][0]
        return super().process_output(stdout, stderr, cmdline=cmdline)


class SaltCpCLI(SaltScriptBase):
    """
    Simple subclass to the salt-cp CLI script
    """

    __cli_timeout_supported__ = True

    def process_output(self, stdout, stderr, cmdline=None):
        if "No minions matched the target. No command was sent, no jid was assigned.\n" in stdout:
            stdout = stdout.split("\n", 1)[1:][0]
        stdout, stderr, json_out = SaltScriptBase.process_output(self, stdout, stderr, cmdline)
        if json_out:
            try:
                return stdout, stderr, json_out[self._minion_tgt]
            except KeyError:
                return stdout, stderr, json_out
        return stdout, stderr, json_out


class SaltKeyCLI(SaltScriptBase):
    """
    Simple subclass to the salt-key CLI script
    """

    _output_replace_re = re.compile(r"((The following keys are going to be.*:|Key for minion.*)\n)")

    # As of Neon, salt-key still does not support --log-level
    # Only when we get the new logging merged in will we get that, so remove that CLI flag
    __cli_log_level_supported__ = SALT_KEY_LOG_LEVEL_SUPPORTED

    def get_minion_tgt(self, kwargs):
        return None

    def process_output(self, stdout, stderr, cmdline=None):
        # salt-key print()s to stdout regardless of output chosen
        stdout = self._output_replace_re.sub("", stdout)
        return super().process_output(stdout, stderr, cmdline=cmdline)


class SaltClient:
    """
    Wrapper class around Salt's local client
    """

    STATE_FUNCTION_RUNNING_RE = re.compile(
        r"""The function (?:"|')(?P<state_func>.*)(?:"|') is running as PID """
        r"(?P<pid>[\d]+) and was started at (?P<date>.*) with jid (?P<jid>[\d]+)"
    )

    def __init__(self, master_config, functions_known_to_return_none=None):
        self.__client = salt.client.get_local_client(mops=master_config)
        if functions_known_to_return_none is None:
            functions_known_to_return_none = (
                "data.get",
                "file.chown",
                "file.chgrp",
                "pkg.refresh_db",
                "ssh.recv_known_host_entries",
                "time.sleep",
            )
        self.__functions_known_to_return_none = functions_known_to_return_none

    def run(self, function, *args, minion_tgt="minion", timeout=300, **kwargs):
        """
        Run a single salt function and condition the return down to match the
        behavior of the raw function call
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
        elif ret[minion_tgt] is None and function not in self.__functions_known_to_return_none:
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
