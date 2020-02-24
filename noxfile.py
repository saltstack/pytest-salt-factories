# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import os
import sys
import tempfile
import textwrap

import nox
from nox.command import CommandFailed
from nox.virtualenv import VirtualEnv


IS_PY3 = sys.version_info > (2,)
COVERAGE_VERSION_REQUIREMENT = "coverage==5.0.3"
SALT_REQUIREMENT = os.environ.get("SALT_REQUIREMENT") or "salt>=3000"
USE_SYSTEM_PYTHON = "USE_SYSTEM_PYTHON" in os.environ

# Be verbose when runing under a CI context
PIP_INSTALL_SILENT = (
    os.environ.get("JENKINS_URL")
    or os.environ.get("CI")
    or os.environ.get("DRONE")
    or os.environ.get("GITHUB_ACTIONS")
) is None
SKIP_REQUIREMENTS_INSTALL = "SKIP_REQUIREMENTS_INSTALL" in os.environ

# Nox options
#  Reuse existing virtualenvs
nox.options.reuse_existing_virtualenvs = True
#  Don't fail on missing interpreters
nox.options.error_on_missing_interpreters = False

# Change to current directory
os.chdir(os.path.dirname(__file__))


def _patch_session(session):
    if USE_SYSTEM_PYTHON is False:
        session.log("NOT Patching nox to install against the system python")
        return

    session.log("Patching nox to install against the system python")
    # Let's get sys.prefix
    old_install_only_value = session._runner.global_config.install_only
    try:
        # Force install only to be false for the following chunk of code
        # For additional information as to why see:
        #   https://github.com/theacodes/nox/pull/181
        session._runner.global_config.install_only = False
        sys_prefix = session.run(
            "python",
            "-c" 'import sys; sys.stdout.write("{}".format(sys.prefix))',
            silent=True,
            log=False,
        )
        # Let's patch nox to make it run and in partcular, install, to the system python
        session._runner.venv = VirtualEnv(
            sys_prefix, interpreter=session._runner.func.python, reuse_existing=True
        )
    finally:
        session._runner.global_config.install_only = old_install_only_value


def _check_crypto_lib_installed(session):
    # Let's get sys.prefix
    old_install_only_value = session._runner.global_config.install_only
    try:
        # Force install only to be false for the following chunk of code
        # For additional information as to why see:
        #   https://github.com/theacodes/nox/pull/181
        session._runner.global_config.install_only = False
        try:
            session.run(
                "python",
                "-c",
                textwrap.dedent(
                    """\
                import sys
                try:
                    from M2Crypto import RSA
                    sys.exit(0)
                except ImportError:
                    sys.exit(1)
                """
                ),
                silent=True,
                log=False,
            )
            session.log("The m2crypto library was found installed")
            session.run("pip", "freeze")
            return
        except CommandFailed:
            session.log("The m2crypto library was NOT found installed")

        try:
            session.run(
                "python",
                "-c",
                textwrap.dedent(
                    """\
                import sys
                try:
                    from Cryptodome.PublicKey import RSA
                    sys.exit(0)
                except ImportError:
                    sys.exit(1)
                """
                ),
                silent=True,
                log=False,
            )
            session.log("The pycryptodome library was found installed")
            session.run("pip", "freeze")
            return
        except CommandFailed:
            session.log("The pycryptodome library was NOT found installed")

        try:
            session.run(
                "python",
                "-c",
                textwrap.dedent(
                    """\
                import sys
                try:
                    from Crypto.Hash import SHA
                    sys.exit(0)
                except ImportError:
                    sys.exit(1)
                """
                ),
                silent=True,
                log=False,
            )
            session.log("The pycrypto or pycryptodomex library was found installed")
            session.run("pip", "freeze")
            return
        except CommandFailed:
            session.log("The pycrypto and pycryptodomex library were NOT found installed")
    finally:
        session._runner.global_config.install_only = old_install_only_value

    session.install("pycryptodome", silent=PIP_INSTALL_SILENT)


def _tests(session):
    """
    Run tests
    """
    if SKIP_REQUIREMENTS_INSTALL is False:
        session.install("-r", "requirements-testing.txt", silent=PIP_INSTALL_SILENT)
        session.install(COVERAGE_VERSION_REQUIREMENT, silent=PIP_INSTALL_SILENT)
        session.install(SALT_REQUIREMENT, silent=PIP_INSTALL_SILENT)
        _check_crypto_lib_installed(session)
        session.install("-e", ".", silent=PIP_INSTALL_SILENT)
    session.run("coverage", "erase")
    args = []
    if session._runner.global_config.forcecolor:
        args.append("--color=yes")
    if not session.posargs:
        args.append("tests/")
    else:
        for arg in session.posargs:
            if arg.startswith("--color") and args[0].startswith("--color"):
                args.pop(0)
            args.append(arg)
    session.run("coverage", "run", "-m", "pytest", "-ra", *args)
    session.notify("coverage")


@nox.session(python=("2", "2.7", "3.5", "3.6", "3.7"))
def tests(session):
    """
    Run tests
    """
    _tests(session)


@nox.session(python=False, name="tests-system-python")
def tests_system_python(session):
    """
    Run tests
    """
    _patch_session(session)
    _tests(session)


@nox.session
def coverage(session):
    """
    Coverage analysis.
    """
    _patch_session(session)
    session.install(COVERAGE_VERSION_REQUIREMENT, silent=PIP_INSTALL_SILENT)
    session.run("coverage", "xml", "-o", "coverage.xml")
    # session.run("coverage", "report", "--fail-under=80", "--show-missing")
    session.run("coverage", "report", "--fail-under=50", "--show-missing")
    session.run("coverage", "erase")


@nox.session(python="3.7")
def blacken(session):
    """
    Run black code formater.
    """
    _patch_session(session)
    session.install(
        "--progress-bar=off", "-r", "requirements-testing.txt", silent=PIP_INSTALL_SILENT
    )
    if session.posargs:
        files = session.posargs
    else:
        files = ["saltfactories", "tests", "noxfile.py", "setup.py"]
    session.run("black", "-l 100", "--exclude=saltfactories/_version.py", *files)

    if session.posargs:
        files = session.posargs
    else:
        files = ["noxfile.py", "setup.py"]
        for directory in ("saltfactories", "tests"):
            for (dirpath, dirnames, filenames) in os.walk(directory):
                for filename in filenames:
                    if not filename.endswith(".py"):
                        continue
                    if filename == "_version.py":
                        continue
                    files.append(os.path.join(dirpath, filename))
    session.run(
        "reorder-python-imports",
        "--py26-plus",
        "--add-import",
        "from __future__ import absolute_import",
        "--add-import",
        "from __future__ import print_function",
        "--add-import",
        "from __future__ import unicode_literals",
        *files
    )


def _lint(session, rcfile, flags, paths):
    _patch_session(session)
    session.install(
        "--progress-bar=off", "-r", "requirements-testing.txt", silent=PIP_INSTALL_SILENT
    )
    session.run("pylint", "--version")
    pylint_report_path = os.environ.get("PYLINT_REPORT")

    cmd_args = ["pylint", "--rcfile={}".format(rcfile)] + list(flags) + list(paths)

    stdout = tempfile.TemporaryFile(mode="w+b")
    lint_failed = False
    try:
        session.run(*cmd_args, stdout=stdout)
    except CommandFailed:
        lint_failed = True
        raise
    finally:
        stdout.seek(0)
        contents = stdout.read()
        if contents:
            if IS_PY3:
                contents = contents.decode("utf-8")
            else:
                contents = contents.encode("utf-8")
            sys.stdout.write(contents)
            sys.stdout.flush()
            if pylint_report_path:
                # Write report
                with open(pylint_report_path, "w") as wfh:
                    wfh.write(contents)
                session.log("Report file written to %r", pylint_report_path)
        stdout.close()


@nox.session(python="3.5")
def lint(session):
    """
    Run PyLint against Salt and it's test suite. Set PYLINT_REPORT to a path to capture output.
    """
    session.notify("lint-code-{}".format(session.python))
    session.notify("lint-tests-{}".format(session.python))


@nox.session(python="3.5", name="lint-code")
def lint_code(session):
    """
    Run PyLint against the code. Set PYLINT_REPORT to a path to capture output.
    """
    flags = ["--disable=I"]
    if session.posargs:
        paths = session.posargs
    else:
        paths = ["setup.py", "noxfile.py", "saltfactories/"]
    _lint(session, ".pylintrc", flags, paths)


@nox.session(python="3.5", name="lint-tests")
def lint_tests(session):
    """
    Run PyLint against Salt and it's test suite. Set PYLINT_REPORT to a path to capture output.
    """
    flags = ["--disable=I"]
    if session.posargs:
        paths = session.posargs
    else:
        paths = ["tests/"]
    _lint(session, ".pylintrc", flags, paths)


@nox.session(python="3")
def docs(session):
    """
    Build Docs
    """
    session.notify("docs-html")


@nox.session(name="docs-html", python="3")
def docs_html(session):
    """
    Build Salt's HTML Documentation
    """
    _patch_session(session)
    session.install(
        "--progress-bar=off", "-r", "requirements-testing.txt", silent=PIP_INSTALL_SILENT
    )
    os.chdir("docs/")
    session.run("make", "clean", external=True)
    session.run("make", "html", "SPHINXOPTS=-W", external=True)
    os.chdir("..")
