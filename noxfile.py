# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import json
import os
import shutil
import sys
import tempfile

import nox
from nox.command import CommandFailed
from nox.virtualenv import VirtualEnv


IS_PY3 = sys.version_info > (2,)
COVERAGE_VERSION_REQUIREMENT = "coverage==5.0.3"
SALT_REQUIREMENT = os.environ.get("SALT_REQUIREMENT") or "salt>=3000.1"
if SALT_REQUIREMENT == "salt==master":
    SALT_REQUIREMENT = "git+https://github.com/saltstack/salt.git@master"
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


def _tests(session):
    """
    Run tests
    """
    if SKIP_REQUIREMENTS_INSTALL is False:
        session.install("-r", os.path.join("requirements", "tests.txt"), silent=PIP_INSTALL_SILENT)
        session.install(COVERAGE_VERSION_REQUIREMENT, silent=PIP_INSTALL_SILENT)
        session.install(SALT_REQUIREMENT, silent=PIP_INSTALL_SILENT)
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


@nox.session(python=("3.5", "3.6", "3.7"))
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
    session.run("coverage", "report", "--fail-under=80", "--show-missing")
    session.run("coverage", "erase")


@nox.session(python="3.7")
def blacken(session):
    """
    Run black code formater.
    """
    _patch_session(session)
    session.install(
        "--progress-bar=off",
        "-r",
        os.path.join("requirements", "lint.txt"),
        silent=PIP_INSTALL_SILENT,
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
        "--progress-bar=off",
        "-r",
        os.path.join("requirements", "lint.txt"),
        silent=PIP_INSTALL_SILENT,
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
    _patch_session(session)
    session.install(
        "--progress-bar=off",
        "-r",
        os.path.join("requirements", "docs.txt"),
        silent=PIP_INSTALL_SILENT,
    )
    os.chdir("docs/")
    session.run("make", "clean", external=True)
    session.notify("docs-linkcheck")
    session.notify("docs-coverage")
    session.notify("docs-html")


@nox.session(name="docs-html", python="3")
def docs_html(session):
    """
    Build Salt's HTML Documentation
    """
    _patch_session(session)
    session.install(
        "--progress-bar=off",
        "-r",
        os.path.join("requirements", "docs.txt"),
        silent=PIP_INSTALL_SILENT,
    )
    os.chdir("docs/")
    session.run("make", "html", "SPHINXOPTS=-W", external=True)


@nox.session(name="docs-linkcheck", python="3")
def docs_linkcheck(session):
    """
    Report Docs Link Check
    """
    _patch_session(session)
    session.install(
        "--progress-bar=off",
        "-r",
        os.path.join("requirements", "docs.txt"),
        silent=PIP_INSTALL_SILENT,
    )
    os.chdir("docs/")
    session.run("make", "linkcheck", "SPHINXOPTS=-W", external=True)
    os.chdir("..")


@nox.session(name="docs-crosslink-info", python="3")
def docs_crosslink_info(session):
    """
    Report intersphinx cross links information
    """
    _patch_session(session)
    session.install(
        "--progress-bar=off",
        "-r",
        os.path.join("requirements", "docs.txt"),
        silent=PIP_INSTALL_SILENT,
    )
    os.chdir("docs/")
    intersphinx_mapping = json.loads(
        session.run(
            "python",
            "-c",
            "import json; import conf; print(json.dumps(conf.intersphinx_mapping))",
            silent=True,
            log=False,
        )
    )
    try:
        mapping_entry = intersphinx_mapping[session.posargs[0]]
    except IndexError:
        session.error(
            "You need to pass at least one argument whose value must be one of: {}".format(
                ", ".join(list(intersphinx_mapping))
            )
        )
    except KeyError:
        session.error(
            "Only acceptable values for first argument are: {}".format(
                ", ".join(list(intersphinx_mapping))
            )
        )
    session.run(
        "python", "-m", "sphinx.ext.intersphinx", mapping_entry[0].rstrip("/") + "/objects.inv"
    )
    os.chdir("..")


@nox.session(name="docs-coverage", python="3")
def docs_coverage(session):
    """
    Report Docs Coverage
    """
    _patch_session(session)
    session.install(
        "--progress-bar=off",
        "-r",
        os.path.join("requirements", "docs.txt"),
        silent=PIP_INSTALL_SILENT,
    )
    os.chdir("docs/")
    session.run("make", "coverage", "SPHINXOPTS=-W", external=True)
    docs_coverage_file = os.path.join("_build", "html", "python.txt")
    if os.path.exists(docs_coverage_file):
        with open(docs_coverage_file) as rfh:
            contents = rfh.readlines()[2:]
            if contents:
                session.error("\n" + "".join(contents))
        return
    session.log("Docs coverage file, {}, does not exit.".format(docs_coverage_file))
    os.chdir("..")


@nox.session(name="gen-api-docs", python="3")
def gen_api_docs_(session):
    """
    Generate API Docs
    """
    _patch_session(session)
    session.install(
        "--progress-bar=off",
        "-r",
        os.path.join("requirements", "docs.txt"),
        silent=PIP_INSTALL_SILENT,
    )
    shutil.rmtree("docs/ref")
    session.run("sphinx-apidoc", "--module-first", "-o", "docs/ref/", "saltfactories/")
