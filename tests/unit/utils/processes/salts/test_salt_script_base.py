# -*- coding: utf-8 -*-
"""
    tests.unit.utils.processes.salts.test_salt_script_base
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test Salt's base script implementation
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import json
import sys

import pytest

from saltfactories.utils.processes.salts import SaltScriptBase


@pytest.fixture
def config_dir(testdir):
    _conf_dir = testdir.mkdir("conf")
    yield _conf_dir
    _conf_dir.remove(rec=1, ignore_errors=True)


@pytest.fixture
def minion_id():
    return "test-minion-id"


@pytest.fixture
def config_file(config_dir, minion_id):
    config_file = config_dir.join("config").strpath
    with open(config_file, "w") as wfh:
        wfh.write("id: {}\n".format(minion_id))
    return config_file


@pytest.fixture
def cli_script_name(testdir):
    py_file = testdir.makepyfile(
        """
        print("This would be the CLI script")
        """
    )
    yield py_file.strpath
    py_file.remove(rec=0, ignore_errors=True)


def test_default_cli_flags(minion_id, config_dir, config_file, cli_script_name):
    config = {"conf_file": config_file}
    args = ["test.ping"]
    kwargs = {"minion_tgt": minion_id}
    expected = [
        sys.executable,
        cli_script_name,
        "--config-dir={}".format(config_dir.strpath),
        "--out=json",
        "--log-level=quiet",
        minion_id,
        "test.ping",
    ]
    proc = SaltScriptBase(cli_script_name, config=config)
    cmdline = proc.build_cmdline(*args, **kwargs)
    assert cmdline == expected


@pytest.mark.parametrize("flag", ["-l", "--log-level", "--log-level="])
def test_override_log_level(minion_id, config_dir, config_file, cli_script_name, flag):
    config = {"conf_file": config_file}
    args = []
    if flag.endswith("="):
        flag_overrides_args = [flag + "info"]
    else:
        flag_overrides_args = [flag, "info"]

    args.extend(flag_overrides_args)
    args.append("test.ping")
    kwargs = {"minion_tgt": minion_id}
    expected = (
        [
            sys.executable,
            cli_script_name,
            "--config-dir={}".format(config_dir.strpath),
            "--out=json",
            minion_id,
        ]
        + flag_overrides_args
        + ["test.ping"]
    )
    proc = SaltScriptBase(cli_script_name, config=config)
    cmdline = proc.build_cmdline(*args, **kwargs)
    assert cmdline == expected


@pytest.mark.parametrize("flag", ["--out", "--output", "--out=", "--output="])
def test_override_output(minion_id, config_dir, config_file, cli_script_name, flag):
    config = {"conf_file": config_file}
    args = []
    if flag.endswith("="):
        flag_overrides_args = [flag + "nested"]
    else:
        flag_overrides_args = [flag, "nested"]

    args.extend(flag_overrides_args)
    args.append("test.ping")
    kwargs = {"minion_tgt": minion_id}
    expected = (
        [
            sys.executable,
            cli_script_name,
            "--config-dir={}".format(config_dir.strpath),
            "--log-level=quiet",
            minion_id,
        ]
        + flag_overrides_args
        + ["test.ping"]
    )
    proc = SaltScriptBase(cli_script_name, config=config)
    cmdline = proc.build_cmdline(*args, **kwargs)
    assert cmdline == expected


def test_default_cli_flags_with_timeout(minion_id, config_dir, config_file, cli_script_name):
    default_timeout = 10
    config = {"conf_file": config_file}
    args = ["test.ping"]
    kwargs = {"minion_tgt": minion_id}
    expected = [
        sys.executable,
        cli_script_name,
        "--config-dir={}".format(config_dir.strpath),
        "--out=json",
        "--log-level=quiet",
        minion_id,
        "test.ping",
        "--timeout={}".format(default_timeout - 5),
    ]
    proc = SaltScriptBase(cli_script_name, config=config, default_timeout=default_timeout)
    # We set __cli_timeout_supported__ to True just to test. This would be an attribute set
    # at the class level for Salt CLI's that support the timeout flag, like for example, salt-run
    proc.__cli_timeout_supported__ = True
    # We set the _terminal_timeout attribute just to test. This attribute would be set when calling
    # SaltScriptBase.run() but we don't really want to call it
    proc._terminal_timeout = proc.default_timeout
    cmdline = proc.build_cmdline(*args, **kwargs)
    assert cmdline == expected


@pytest.mark.parametrize("flag", ["-t", "--timeout", "--timeout="])
def test_override_timeout(minion_id, config_dir, config_file, cli_script_name, flag):
    flag_value = 15
    if flag.endswith("="):
        flag_overrides_args = [flag + str(flag_value)]
    else:
        flag_overrides_args = [flag, str(flag_value)]

    default_timeout = 10
    config = {"conf_file": config_file}
    args = flag_overrides_args + ["test.ping"]
    kwargs = {"minion_tgt": minion_id}
    expected = (
        [
            sys.executable,
            cli_script_name,
            "--config-dir={}".format(config_dir.strpath),
            "--out=json",
            "--log-level=quiet",
            minion_id,
        ]
        + flag_overrides_args
        + ["test.ping",]
    )
    proc = SaltScriptBase(cli_script_name, config=config, default_timeout=default_timeout)
    # We set __cli_timeout_supported__ to True just to test. This would be an attribute set
    # at the class level for Salt CLI's that support the timeout flag, like for example, salt-run
    proc.__cli_timeout_supported__ = True
    # We set the _terminal_timeout attribute just to test. This attribute would be set when calling
    # SaltScriptBase.run() but we don't really want to call it
    proc._terminal_timeout = flag_value
    cmdline = proc.build_cmdline(*args, **kwargs)
    assert cmdline == expected
    # Let's also confirm that we also parsed the timeout flag value and set the SaltScriptBase
    # _terminal_timeout to that value plus 5
    assert proc._terminal_timeout == flag_value + 5


@pytest.mark.parametrize("flag", ["-t", "--timeout", "--timeout="])
def test_override_timeout_bad_value(minion_id, config_dir, config_file, cli_script_name, flag):
    flag_value = 15
    if flag.endswith("="):
        flag_overrides_args = [flag + str(flag_value) + "i"]
    else:
        flag_overrides_args = [flag, str(flag_value) + "i"]

    default_timeout = 10
    config = {"conf_file": config_file}
    args = flag_overrides_args + ["test.ping"]
    kwargs = {"minion_tgt": minion_id}
    expected = (
        [
            sys.executable,
            cli_script_name,
            "--config-dir={}".format(config_dir.strpath),
            "--out=json",
            "--log-level=quiet",
            minion_id,
        ]
        + flag_overrides_args
        + ["test.ping",]
    )
    proc = SaltScriptBase(cli_script_name, config=config, default_timeout=default_timeout)
    # We set __cli_timeout_supported__ to True just to test. This would be an attribute set
    # at the class level for Salt CLI's that support the timeout flag, like for example, salt-run
    proc.__cli_timeout_supported__ = True
    # We set the _terminal_timeout attribute just to test. This attribute would be set when calling
    # SaltScriptBase.run() but we don't really want to call it
    proc._terminal_timeout = flag_value
    cmdline = proc.build_cmdline(*args, **kwargs)
    assert cmdline == expected
    # Let's confirm that even though we tried to parse the timeout flag value, it was a bad value and the
    # SaltScriptBase _terminal_timeout attribute was not update
    assert proc._terminal_timeout == flag_value


def test_process_output(cli_script_name):
    in_stdout = '"The salt master could not be contacted. Is master running?"\n'
    in_stderr = ""
    cmdline = ["--out=json"]
    proc = SaltScriptBase(cli_script_name)
    stdout, stderr, json_out = proc.process_output(in_stdout, in_stderr, cmdline=cmdline)
    assert stdout == json.loads(in_stdout)
    assert stderr == in_stderr
    assert json_out is None
