"""
Code to generate Salt CLI scripts for test runs.
"""
import logging
import pathlib
import stat
import textwrap

import pytest

log = logging.getLogger(__name__)

SCRIPT_TEMPLATES = {
    "salt": textwrap.dedent(
        """
        import atexit
        import traceback
        from salt.scripts import salt_main

        if __name__ == '__main__':
            exitcode = 0
            try:
                salt_main()
            except SystemExit as exc:
                exitcode = exc.code
                # https://docs.python.org/3/library/exceptions.html#SystemExit
                if exitcode is None:
                    exitcode = 0
                if not isinstance(exitcode, int):
                    # A string?!
                    sys.stderr.write(exitcode)
                    exitcode = 1
            except Exception as exc:
                sys.stderr.write(
                    "An un-handled exception was caught: " + str(exc) + "\\n" + traceback.format_exc()
                )
                exitcode = 1
            sys.stdout.flush()
            sys.stderr.flush()
            atexit._run_exitfuncs()
            os._exit(exitcode)
        """
    ),
    "salt-api": textwrap.dedent(
        """
        import atexit
        import traceback
        import salt.cli.api
        import salt.utils.process

        salt.utils.process.notify_systemd()

        def main():
            sapi = salt.cli.api.SaltAPI()
            sapi.start()

        if __name__ == '__main__':
            exitcode = 0
            try:
                main()
            except SystemExit as exc:
                exitcode = exc.code
                # https://docs.python.org/3/library/exceptions.html#SystemExit
                if exitcode is None:
                    exitcode = 0
                if not isinstance(exitcode, int):
                    # A string?!
                    sys.stderr.write(exitcode)
                    exitcode = 1
            except Exception as exc:
                sys.stderr.write(
                    "An un-handled exception was caught: " + str(exc) + "\\n" + traceback.format_exc()
                )
                exitcode = 1
            sys.stdout.flush()
            sys.stderr.flush()
            atexit._run_exitfuncs()
            os._exit(exitcode)
        """
    ),
    "common": textwrap.dedent(
        """
        import atexit
        import traceback
        from salt.scripts import salt_{0}

        def main():
            if sys.platform.startswith("win"):
                import os.path
                import py_compile
                cfile = os.path.splitext(__file__)[0] + '.pyc'
                if not os.path.exists(cfile):
                    py_compile.compile(__file__, cfile)
            salt_{0}()

        if __name__ == '__main__':
            exitcode = 0
            try:
                main()
            except SystemExit as exc:
                exitcode = exc.code
                # https://docs.python.org/3/library/exceptions.html#SystemExit
                if exitcode is None:
                    exitcode = 0
                if not isinstance(exitcode, int):
                    # A string?!
                    sys.stderr.write(exitcode)
                    exitcode = 1
            except Exception as exc:
                sys.stderr.write(
                    "An un-handled exception was caught: " + str(exc) + "\\n" + traceback.format_exc()
                )
                exitcode = 1
            sys.stdout.flush()
            sys.stderr.flush()
            atexit._run_exitfuncs()
            os._exit(exitcode)
        """
    ),
    "coverage": textwrap.dedent(
        """
        # Setup coverage environment variables
        COVERAGE_FILE = os.path.join(CODE_DIR, '.coverage')
        COVERAGE_PROCESS_START = os.path.join(CODE_DIR, '.coveragerc')
        os.environ[str('COVERAGE_FILE')] = str(COVERAGE_FILE)
        os.environ[str('COVERAGE_PROCESS_START')] = str(COVERAGE_PROCESS_START)
        """
    ),
    "sitecustomize": textwrap.dedent(
        """
        # Allow sitecustomize.py to be importable for test coverage purposes
        SITECUSTOMIZE_DIR = r'{sitecustomize_dir}'
        PYTHONPATH = os.environ.get('PYTHONPATH') or None
        if PYTHONPATH is None:
            PYTHONPATH_ENV_VAR = SITECUSTOMIZE_DIR
        else:
            PYTHON_PATH_ENTRIES = PYTHONPATH.split(os.pathsep)
            if SITECUSTOMIZE_DIR in PYTHON_PATH_ENTRIES:
                PYTHON_PATH_ENTRIES.remove(SITECUSTOMIZE_DIR)
            PYTHON_PATH_ENTRIES.insert(0, SITECUSTOMIZE_DIR)
            PYTHONPATH_ENV_VAR = os.pathsep.join(PYTHON_PATH_ENTRIES)
        os.environ[str('PYTHONPATH')] = str(PYTHONPATH_ENV_VAR)
        if SITECUSTOMIZE_DIR in sys.path:
            sys.path.remove(SITECUSTOMIZE_DIR)
        sys.path.insert(0, SITECUSTOMIZE_DIR)
        """
    ),
}


def generate_script(
    bin_dir,
    script_name,
    code_dir=None,
    inject_coverage=False,
    inject_sitecustomize=False,
):
    """
    Generate a CLI script.

    :param ~pathlib.Path bin_dir: The path to the directory which will contain the CLI scripts
    :param str script_name: The CLI script name
    :param ~pathlib.Path code_dir: The project's being tested root directory path
    :param bool inject_coverage: Inject code to track code coverage
    :param bool inject_sitecustomize: Inject code to support code coverage in subprocesses
    """
    if isinstance(bin_dir, str):
        bin_dir = pathlib.Path(bin_dir)
    bin_dir.mkdir(exist_ok=True)

    cli_script_name = "cli_{}.py".format(script_name.replace("-", "_"))
    script_path = bin_dir / cli_script_name

    if not script_path.is_file():
        log.info("Generating %s", script_path)

        with script_path.open("w") as sfh:
            script_template = SCRIPT_TEMPLATES.get(script_name, None)
            if script_template is None:
                script_template = SCRIPT_TEMPLATES.get("common", None)

            script_contents = (
                textwrap.dedent(
                    """
                from __future__ import absolute_import
                import os
                import sys

                # We really do not want buffered output
                os.environ[str("PYTHONUNBUFFERED")] = str("1")
                # Don't write .pyc files or create them in __pycache__ directories
                os.environ[str("PYTHONDONTWRITEBYTECODE")] = str("1")
                """
                ).strip()
                + "\n\n"
            )

            if code_dir:
                script_contents += (
                    textwrap.dedent(
                        """
                    CODE_DIR = r'{code_dir}'
                    if CODE_DIR in sys.path:
                        sys.path.remove(CODE_DIR)
                    sys.path.insert(0, CODE_DIR)""".format(
                            code_dir=code_dir
                        )
                    ).strip()
                    + "\n\n"
                )

            if inject_coverage and not code_dir:
                raise pytest.UsageError(
                    "The inject coverage code needs to know the code root to find the "
                    "path to the '.coveragerc' file. Please pass 'code_dir'."
                )
            if inject_coverage:
                script_contents += SCRIPT_TEMPLATES["coverage"].strip() + "\n\n"

            if inject_sitecustomize:
                script_contents += (
                    SCRIPT_TEMPLATES["sitecustomize"]
                    .format(
                        sitecustomize_dir=str(pathlib.Path(__file__).resolve().parent / "coverage")
                    )
                    .strip()
                    + "\n\n"
                )

            script_contents += (
                script_template.format(script_name.replace("salt-", "").replace("-", "_")).strip()
                + "\n"
            )
            sfh.write(script_contents)
            log.debug(
                "Wrote the following contents to temp script %s:\n%s", script_path, script_contents
            )
        fst = script_path.stat()
        script_path.chmod(fst.st_mode | stat.S_IEXEC)

    log.info("Returning script path %r", script_path)
    return str(script_path)
