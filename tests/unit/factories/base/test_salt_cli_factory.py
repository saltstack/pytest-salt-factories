import json
import os
import shutil
import sys
from collections import OrderedDict
from unittest import mock

import pytest
from pytestshellutils.utils.processes import ProcessResult

from saltfactories.bases import SALT_TIMEOUT_FLAG_INCREASE
from saltfactories.bases import SaltCli


@pytest.fixture
def config_dir(pytester):
    _conf_dir = pytester.mkdir("conf")
    try:
        yield _conf_dir
    finally:
        shutil.rmtree(str(_conf_dir), ignore_errors=True)


@pytest.fixture
def minion_id():
    return "test-minion-id"


@pytest.fixture
def config_file(config_dir, minion_id):
    config_file = str(config_dir / "config")
    with open(config_file, "w") as wfh:
        wfh.write("id: {}\n".format(minion_id))
    return config_file


@pytest.fixture
def cli_script_name(pytester):
    py_file = pytester.makepyfile(
        """
        print("This would be the CLI script")
        """
    )
    try:
        yield str(py_file)
    finally:
        py_file.unlink()


def test_default_cli_flags(minion_id, config_dir, config_file, cli_script_name):
    config = {"conf_file": config_file, "id": "the-id"}
    args = ["test.ping"]
    kwargs = {"minion_tgt": minion_id}
    expected = [
        sys.executable,
        cli_script_name,
        "--config-dir={}".format(config_dir),
        "--out=json",
        "--out-indent=0",
        "--log-level=critical",
        minion_id,
        "test.ping",
    ]
    proc = SaltCli(script_name=cli_script_name, config=config)
    cmdline = proc.cmdline(*args, **kwargs)
    assert cmdline == expected


@pytest.mark.parametrize("flag", ["-l", "--log-level", "--log-level="])
def test_override_log_level(minion_id, config_dir, config_file, cli_script_name, flag):
    config = {"conf_file": config_file, "id": "the-id"}
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
            "--config-dir={}".format(config_dir),
            "--out=json",
            "--out-indent=0",
            minion_id,
        ]
        + flag_overrides_args
        + ["test.ping"]
    )
    proc = SaltCli(script_name=cli_script_name, config=config)
    cmdline = proc.cmdline(*args, **kwargs)
    assert cmdline == expected


@pytest.mark.parametrize("flag", ["--out", "--output", "--out=", "--output="])
def test_override_output(minion_id, config_dir, config_file, cli_script_name, flag):
    config = {"conf_file": config_file, "id": "the-id"}
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
            "--config-dir={}".format(config_dir),
            "--log-level=critical",
            minion_id,
        ]
        + flag_overrides_args
        + ["test.ping"]
    )
    proc = SaltCli(script_name=cli_script_name, config=config)
    cmdline = proc.cmdline(*args, **kwargs)
    assert cmdline == expected


@pytest.mark.parametrize(
    "flag", ["--out-indent", "--output-indent", "--out-indent=", "--output-indent="]
)
def test_override_output_indent(minion_id, config_dir, config_file, cli_script_name, flag):
    config = {"conf_file": config_file, "id": "the-id"}
    args = []
    if flag.endswith("="):
        flag_overrides_args = [flag + "1"]
    else:
        flag_overrides_args = [flag, "1"]

    args.extend(flag_overrides_args)
    args.append("test.ping")
    kwargs = {"minion_tgt": minion_id}
    expected = (
        [
            sys.executable,
            cli_script_name,
            "--config-dir={}".format(config_dir),
            "--out=json",
            "--log-level=critical",
            minion_id,
        ]
        + flag_overrides_args
        + ["test.ping"]
    )
    proc = SaltCli(script_name=cli_script_name, config=config)
    cmdline = proc.cmdline(*args, **kwargs)
    assert cmdline == expected


def test_cli_timeout_lesser_than_timeout_kw(minion_id, config_dir, config_file, cli_script_name):
    # Both --timeout and _timeout are passed.
    # Since --timeout is less than _timeout, the value of _timeout does not changed
    timeout = 10
    explicit_timeout = 60
    cli_timeout = 6
    config = {"conf_file": config_file, "id": "the-id"}
    args = ["--timeout", str(cli_timeout), "test.ping"]
    kwargs = {"minion_tgt": minion_id, "_timeout": explicit_timeout}
    expected = [
        sys.executable,
        cli_script_name,
        "--config-dir={}".format(config_dir),
        "--out=json",
        "--out-indent=0",
        "--log-level=critical",
        minion_id,
        "--timeout",
        "6",
        "test.ping",
    ]

    popen_mock = mock.MagicMock()
    popen_mock.pid = os.getpid()
    popen_mock.poll = mock.MagicMock(side_effect=[None, None, None, None, True])
    terminate_mock = mock.MagicMock(
        return_value=ProcessResult(returncode=0, stdout="", stderr="", cmdline=())
    )
    popen_mock.terminate = terminate_mock

    proc = SaltCli(script_name=cli_script_name, config=config, timeout=timeout)
    with mock.patch.object(proc.impl, "init_terminal", popen_mock), mock.patch.object(
        proc, "terminate", terminate_mock
    ):
        proc.impl._terminal = popen_mock
        # We set __cli_timeout_supported__ to True just to test. This would be an attribute set
        # at the class level for Salt CLI's that support the timeout flag, like for example, salt-run
        proc.__cli_timeout_supported__ = True
        proc.run(*args, **kwargs)
        assert proc.impl._terminal_timeout == explicit_timeout
        assert popen_mock.call_args[0][0] == expected  # pylint: disable=unsubscriptable-object


def test_cli_timeout_matches_timeout_kw(minion_id, config_dir, config_file, cli_script_name):
    # Both --timeout and _timeout are passed.
    # Since --timeout is greater than _timeout, the value of _timeout is updated to the value of --timeout plus 5
    timeout = 10
    explicit_timeout = 20
    cli_timeout = 20
    config = {"conf_file": config_file, "id": "the-id"}
    args = ["--timeout", str(cli_timeout), "test.ping"]
    kwargs = {"minion_tgt": minion_id, "_timeout": explicit_timeout}
    expected = [
        sys.executable,
        cli_script_name,
        "--config-dir={}".format(config_dir),
        "--out=json",
        "--out-indent=0",
        "--log-level=critical",
        minion_id,
        "--timeout",
        "20",
        "test.ping",
    ]

    popen_mock = mock.MagicMock()
    popen_mock.pid = os.getpid()
    popen_mock.poll = mock.MagicMock(side_effect=[None, None, None, None, True])
    terminate_mock = mock.MagicMock(
        return_value=ProcessResult(returncode=0, stdout="", stderr="", cmdline=())
    )
    popen_mock.terminate = terminate_mock

    proc = SaltCli(script_name=cli_script_name, config=config, timeout=timeout)
    with mock.patch.object(proc.impl, "init_terminal", popen_mock), mock.patch.object(
        proc, "terminate", terminate_mock
    ):
        proc.impl._terminal = popen_mock
        # We set __cli_timeout_supported__ to True just to test. This would be an attribute set
        # at the class level for Salt CLI's that support the timeout flag, like for example, salt-run
        proc.__cli_timeout_supported__ = True
        proc.run(*args, **kwargs)
        assert proc.impl._terminal_timeout == cli_timeout + SALT_TIMEOUT_FLAG_INCREASE
        assert popen_mock.call_args[0][0] == expected  # pylint: disable=unsubscriptable-object


def test_cli_timeout_greater_than_timeout_kw(minion_id, config_dir, config_file, cli_script_name):
    # Both --timeout and _timeout are passed.
    # Since --timeout is greater than _timeout, the value of _timeout is updated to the value of --timeout plus 5
    timeout = 10
    explicit_timeout = 20
    cli_timeout = 60
    config = {"conf_file": config_file, "id": "the-id"}
    args = ["--timeout", str(cli_timeout), "test.ping"]
    kwargs = {"minion_tgt": minion_id, "_timeout": explicit_timeout}
    expected = [
        sys.executable,
        cli_script_name,
        "--config-dir={}".format(config_dir),
        "--out=json",
        "--out-indent=0",
        "--log-level=critical",
        minion_id,
        "--timeout",
        "60",
        "test.ping",
    ]

    popen_mock = mock.MagicMock()
    popen_mock.pid = os.getpid()
    popen_mock.poll = mock.MagicMock(side_effect=[None, None, None, None, True])
    terminate_mock = mock.MagicMock(
        return_value=ProcessResult(returncode=0, stdout="", stderr="", cmdline=())
    )
    popen_mock.terminate = terminate_mock

    proc = SaltCli(script_name=cli_script_name, config=config, timeout=timeout)
    with mock.patch.object(proc.impl, "init_terminal", popen_mock), mock.patch.object(
        proc, "terminate", terminate_mock
    ):
        proc.impl._terminal = popen_mock
        # We set __cli_timeout_supported__ to True just to test. This would be an attribute set
        # at the class level for Salt CLI's that support the timeout flag, like for example, salt-run
        proc.__cli_timeout_supported__ = True
        proc.run(*args, **kwargs)
        assert proc.impl._terminal_timeout == cli_timeout + SALT_TIMEOUT_FLAG_INCREASE
        assert popen_mock.call_args[0][0] == expected  # pylint: disable=unsubscriptable-object


def test_cli_timeout_updates_to_timeout_kw_plus_10(
    minion_id, config_dir, config_file, cli_script_name
):
    # _timeout is passed, the value of --timeout is _timeout, internal timeout is added 10 seconds
    timeout = 10
    explicit_timeout = 60
    config = {"conf_file": config_file, "id": "the-id"}
    args = ["test.ping"]
    kwargs = {"minion_tgt": minion_id, "_timeout": explicit_timeout}
    expected = [
        sys.executable,
        cli_script_name,
        "--config-dir={}".format(config_dir),
        "--timeout={}".format(explicit_timeout),
        "--out=json",
        "--out-indent=0",
        "--log-level=critical",
        minion_id,
        "test.ping",
    ]

    popen_mock = mock.MagicMock()
    popen_mock.pid = os.getpid()
    popen_mock.poll = mock.MagicMock(side_effect=[None, None, None, None, True])
    popen_mock.terminate = mock.MagicMock(
        return_value=ProcessResult(returncode=0, stdout="", stderr="", cmdline=())
    )
    terminate_mock = mock.MagicMock(return_value=ProcessResult(returncode=0, stdout="", stderr=""))

    proc = SaltCli(script_name=cli_script_name, config=config, timeout=timeout)
    with mock.patch.object(proc.impl, "init_terminal", popen_mock), mock.patch.object(
        proc, "terminate", terminate_mock
    ):
        proc.impl._terminal = popen_mock
        # We set __cli_timeout_supported__ to True just to test. This would be an attribute set
        # at the class level for Salt CLI's that support the timeout flag, like for example, salt-run
        proc.__cli_timeout_supported__ = True
        proc.run(*args, **kwargs)
        assert proc.impl._terminal_timeout == explicit_timeout + SALT_TIMEOUT_FLAG_INCREASE
        assert popen_mock.call_args[0][0] == expected  # pylint: disable=unsubscriptable-object


def test_cli_timeout_updates_to_default_timeout_plus_10(
    minion_id, config_dir, config_file, cli_script_name
):
    # Neither _timeout nor --timeout are passed, --timeout equals the default timeout, internal timeout is added 10
    timeout = 10
    config = {"conf_file": config_file, "id": "the-id"}
    args = ["test.ping"]
    kwargs = {"minion_tgt": minion_id}
    expected = [
        sys.executable,
        cli_script_name,
        "--config-dir={}".format(config_dir),
        "--timeout={}".format(timeout),
        "--out=json",
        "--out-indent=0",
        "--log-level=critical",
        minion_id,
        "test.ping",
    ]

    popen_mock = mock.MagicMock()
    popen_mock.pid = os.getpid()
    popen_mock.poll = mock.MagicMock(side_effect=[None, None, None, None, True])
    popen_mock.terminate = mock.MagicMock(
        return_value=ProcessResult(returncode=0, stdout="", stderr="", cmdline=())
    )
    terminate_mock = mock.MagicMock(return_value=ProcessResult(returncode=0, stdout="", stderr=""))

    proc = SaltCli(script_name=cli_script_name, config=config, timeout=timeout)
    with mock.patch.object(proc.impl, "init_terminal", popen_mock), mock.patch.object(
        proc, "terminate", terminate_mock
    ):
        proc.impl._terminal = popen_mock
        # We set __cli_timeout_supported__ to True just to test. This would be an attribute set
        # at the class level for Salt CLI's that support the timeout flag, like for example, salt-run
        proc.__cli_timeout_supported__ = True
        proc.run(*args, **kwargs)
        assert proc.impl._terminal_timeout == timeout + SALT_TIMEOUT_FLAG_INCREASE
        assert popen_mock.call_args[0][0] == expected  # pylint: disable=unsubscriptable-object


@pytest.mark.parametrize("flag", ["-t", "--timeout", "--timeout="])
def test_override_timeout(minion_id, config_dir, config_file, cli_script_name, flag):
    flag_value = 15
    if flag.endswith("="):
        flag_overrides_args = [flag + str(flag_value)]
    else:
        flag_overrides_args = [flag, str(flag_value)]

    timeout = 10
    config = {"conf_file": config_file, "id": "the-id"}
    args = flag_overrides_args + ["test.ping"]
    kwargs = {"minion_tgt": minion_id}
    expected = (
        [
            sys.executable,
            cli_script_name,
            "--config-dir={}".format(config_dir),
            "--out=json",
            "--out-indent=0",
            "--log-level=critical",
            minion_id,
        ]
        + flag_overrides_args
        + ["test.ping"]
    )
    proc = SaltCli(script_name=cli_script_name, config=config, timeout=timeout)
    # We set __cli_timeout_supported__ to True just to test. This would be an attribute set
    # at the class level for Salt CLI's that support the timeout flag, like for example, salt-run
    proc.__cli_timeout_supported__ = True
    # We set the _terminal_timeout attribute just to test. This attribute would be set when calling
    # SaltScriptBase.run() but we don't really want to call it
    proc.impl._terminal_timeout = flag_value
    cmdline = proc.cmdline(*args, **kwargs)
    assert cmdline == expected
    # Let's also confirm that we also parsed the timeout flag value and set the SaltScriptBase
    # _terminal_timeout to that value plus 10
    assert proc.impl._terminal_timeout == flag_value + SALT_TIMEOUT_FLAG_INCREASE


@pytest.mark.parametrize("flag", ["-t", "--timeout", "--timeout="])
def test_override_timeout_bad_value(minion_id, config_dir, config_file, cli_script_name, flag):
    flag_value = 15
    if flag.endswith("="):
        flag_overrides_args = [flag + str(flag_value) + "i"]
    else:
        flag_overrides_args = [flag, str(flag_value) + "i"]

    timeout = 10
    config = {"conf_file": config_file, "id": "the-id"}
    args = flag_overrides_args + ["test.ping"]
    kwargs = {"minion_tgt": minion_id}
    expected = (
        [
            sys.executable,
            cli_script_name,
            "--config-dir={}".format(config_dir),
            "--out=json",
            "--out-indent=0",
            "--log-level=critical",
            minion_id,
        ]
        + flag_overrides_args
        + ["test.ping"]
    )
    proc = SaltCli(script_name=cli_script_name, config=config, timeout=timeout)
    # We set __cli_timeout_supported__ to True just to test. This would be an attribute set
    # at the class level for Salt CLI's that support the timeout flag, like for example, salt-run
    proc.__cli_timeout_supported__ = True
    # We set the _terminal_timeout attribute just to test. This attribute would be set when calling
    # SaltScriptBase.run() but we don't really want to call it
    proc.impl._terminal_timeout = timeout
    cmdline = proc.cmdline(*args, **kwargs)
    assert cmdline == expected
    # Let's confirm that even though we tried to parse the timeout flag value, it was a bad value and the
    # SaltScriptBase _terminal_timeout attribute was not update
    assert proc.impl._terminal_timeout == timeout


@pytest.mark.parametrize("flag", ["-c", "--config-dir", "--config-dir=", None])
def test_override_config_dir(minion_id, config_dir, config_file, cli_script_name, flag):
    passed_config_dir = "{}.new".format(config_dir)
    if flag is None:
        flag_overrides_args = ["--config-dir={}".format(config_dir)]
    elif flag.endswith("="):
        flag_overrides_args = [flag + passed_config_dir]
    else:
        flag_overrides_args = [flag, passed_config_dir]

    config = {"conf_file": config_file, "id": "the-id"}
    args = flag_overrides_args + ["test.ping"]
    kwargs = {"minion_tgt": minion_id}
    expected = (
        [
            sys.executable,
            cli_script_name,
            "--out=json",
            "--out-indent=0",
            "--log-level=critical",
            minion_id,
        ]
        + flag_overrides_args
        + ["test.ping"]
    )
    proc = SaltCli(script_name=cli_script_name, config=config)
    cmdline = proc.cmdline(*args, **kwargs)
    assert cmdline == expected


def test_process_output(cli_script_name, config_file):
    in_stdout = '"The salt master could not be contacted. Is master running?"\n'
    in_stderr = ""
    cmdline = ["--out=json"]
    config = {"conf_file": config_file, "id": "the-id"}
    proc = SaltCli(script_name=cli_script_name, config=config)
    # Call proc.cmdline() so that proc.__json_output__ is properly set
    proc.cmdline()
    stdout, stderr, json_out = proc.process_output(in_stdout, in_stderr, cmdline=cmdline)
    assert stdout == json.loads(in_stdout)
    assert stderr == in_stderr
    assert json_out is None


def test_non_string_cli_flags(minion_id, config_dir, config_file, cli_script_name):
    config = {"conf_file": config_file, "id": "the-id"}
    args = ["test.ping"]
    foo = ["the", "foo", "list"]
    kwargs = {"minion_tgt": minion_id, "foo": foo}
    expected = [
        sys.executable,
        cli_script_name,
        "--config-dir={}".format(config_dir),
        "--out=json",
        "--out-indent=0",
        "--log-level=critical",
        minion_id,
        "test.ping",
        "foo={}".format(json.dumps(foo)),
    ]
    proc = SaltCli(script_name=cli_script_name, config=config)
    cmdline = proc.cmdline(*args, **kwargs)
    assert cmdline == expected


def test_jsonify_kwargs(minion_id, config_dir, config_file, cli_script_name):
    config = {"conf_file": config_file, "id": "the-id"}
    args = ["test.ping"]
    # Strings
    extra_kwargs = OrderedDict((("look", "Ma"), ("no", "Hands!")))
    kwargs = OrderedDict((("minion_tgt", minion_id),))
    kwargs.update(extra_kwargs)
    expected = [
        sys.executable,
        cli_script_name,
        "--config-dir={}".format(config_dir),
        "--out=json",
        "--out-indent=0",
        "--log-level=critical",
        minion_id,
        "test.ping",
    ]
    for key, value in extra_kwargs.items():
        expected.append("{}={}".format(key, value))
    proc = SaltCli(script_name=cli_script_name, config=config)
    cmdline = proc.cmdline(*args, **kwargs)
    # Function **kwargs are not ordered dictionaries on some python versions
    # let's just use sorted to make sure everything is in the output
    assert sorted(cmdline) == sorted(expected)

    # Numbers
    extra_kwargs = OrderedDict((("width", 1.27), ("height", 3)))
    kwargs = OrderedDict((("minion_tgt", minion_id),))
    kwargs.update(extra_kwargs)
    expected = [
        sys.executable,
        cli_script_name,
        "--config-dir={}".format(config_dir),
        "--out=json",
        "--out-indent=0",
        "--log-level=critical",
        minion_id,
        "test.ping",
    ]
    for key, value in extra_kwargs.items():
        value = json.dumps(value)
        expected.append("{}={}".format(key, value))
    proc = SaltCli(script_name=cli_script_name, config=config)
    cmdline = proc.cmdline(*args, **kwargs)
    # Function **kwargs are not ordered dictionaries on some python versions
    # let's just use sorted to make sure everything is in the output
    assert sorted(cmdline) == sorted(expected)

    # Booleans
    extra_kwargs = OrderedDict((("short", False), ("tall", True)))
    kwargs = OrderedDict((("minion_tgt", minion_id),))
    kwargs.update(extra_kwargs)
    expected = [
        sys.executable,
        cli_script_name,
        "--config-dir={}".format(config_dir),
        "--out=json",
        "--out-indent=0",
        "--log-level=critical",
        minion_id,
        "test.ping",
    ]
    for key, value in extra_kwargs.items():
        value = json.dumps(value)
        expected.append("{}={}".format(key, value))
    proc = SaltCli(script_name=cli_script_name, config=config)
    cmdline = proc.cmdline(*args, **kwargs)
    # Function **kwargs are not ordered dictionaries on some python versions
    # let's just use sorted to make sure everything is in the output
    assert sorted(cmdline) == sorted(expected)

    # JSon structure
    extra_kwargs = {"look": "Ma", "no": "Hands!"}
    kwargs = {"minion_tgt": minion_id, "extra": extra_kwargs}
    expected = [
        sys.executable,
        cli_script_name,
        "--config-dir={}".format(config_dir),
        "--out=json",
        "--out-indent=0",
        "--log-level=critical",
        minion_id,
        "test.ping",
        "extra={}".format(json.dumps(extra_kwargs)),
    ]
    proc = SaltCli(script_name=cli_script_name, config=config)
    cmdline = proc.cmdline(*args, **kwargs)
    # Function **kwargs are not ordered dictionaries on some python versions
    # let's just use sorted to make sure everything is in the output
    assert sorted(cmdline) == sorted(expected)


def test_salt_cli_factory_id_attr_comes_first_in_repr(config_file):
    proc = SaltCli(script_name="foo-bar", config={"id": "TheID", "conf_file": config_file})
    regex = r"{}(id='TheID'".format(proc.__class__.__name__)
    assert repr(proc).startswith(regex)
    assert str(proc).startswith(regex)


def test_salt_cli_display_name(config_file):
    factory_id = "TheID"
    proc = SaltCli(script_name="foo-bar", config={"id": factory_id, "conf_file": config_file})
    assert proc.get_display_name() == "{}(id={!r})".format(SaltCli.__name__, factory_id)
