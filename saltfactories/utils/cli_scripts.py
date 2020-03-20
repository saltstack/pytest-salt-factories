# -*- coding: utf-8 -*-
"""
saltfactories.utils.cli_scripts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Code to generate Salt CLI scripts for test runs
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import stat
import sys
import textwrap

try:
    import salt.utils.files
except ImportError:  # pragma: no cover
    # We need salt to test salt with saltfactories, and, when pytest is rewriting modules for proper assertion
    # reporting, we still haven't had a chance to inject the salt path into sys.modules, so we'll hit this
    # import error, but its safe to pass
    pass

log = logging.getLogger(__name__)

SCRIPT_TEMPLATES = {
    "salt": textwrap.dedent(
        """
        import atexit
        from salt.scripts import salt_main

        if __name__ == '__main__':
            exitcode = 0
            try:
                salt_main()
            except SystemExit as exc:
                exitcode = exc.code
            sys.stdout.flush()
            sys.stderr.flush()
            atexit._run_exitfuncs()
            os._exit(exitcode)
        """
    ),
    "salt-api": textwrap.dedent(
        """
        import atexit
        import salt.cli

        def main():
            sapi = salt.cli.SaltAPI()
            sapi.start()

        if __name__ == '__main__':
            exitcode = 0
            try:
                main()
            except SystemExit as exc:
                exitcode = exc.code
            sys.stdout.flush()
            sys.stderr.flush()
            atexit._run_exitfuncs()
            os._exit(exitcode)
        """
    ),
    "common": textwrap.dedent(
        """
        import atexit
        from salt.scripts import salt_{0}
        import salt.utils.platform

        def main():
            if salt.utils.platform.is_windows():
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
    executable=None,
    code_dir=None,
    inject_coverage=False,
    inject_sitecustomize=False,
):
    """
    Generate script
    """
    if not os.path.isdir(bin_dir):
        os.makedirs(bin_dir)

    cli_script_name = "cli_{}.py".format(script_name.replace("-", "_"))
    script_path = os.path.join(bin_dir, cli_script_name)

    if not os.path.isfile(script_path):
        log.info("Generating %s", script_path)

        with salt.utils.files.fopen(script_path, "w") as sfh:
            script_template = SCRIPT_TEMPLATES.get(script_name, None)
            if script_template is None:
                script_template = SCRIPT_TEMPLATES.get("common", None)

            if executable and len(executable) > 128:
                # Too long for a shebang, let's use /usr/bin/env and hope
                # the right python is picked up
                executable = "/usr/bin/env python"

            script_contents = (
                textwrap.dedent(
                    """
                #!{executable}

                from __future__ import absolute_import
                import os
                import sys

                # We really do not want buffered output
                os.environ[str("PYTHONUNBUFFERED")] = str("1")
                # Don't write .pyc files or create them in __pycache__ directories
                os.environ[str("PYTHONDONTWRITEBYTECODE")] = str("1")
                """.format(
                        executable=executable or sys.executable
                    )
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
                raise RuntimeError(
                    "The inject coverage code needs to know the code root to find the "
                    "path to the '.coveragerc' file. Please pass 'code_dir'."
                )
            if inject_coverage:
                script_contents += SCRIPT_TEMPLATES["coverage"].strip() + "\n\n"

            if inject_sitecustomize:
                script_contents += (
                    SCRIPT_TEMPLATES["sitecustomize"]
                    .format(sitecustomize_dir=os.path.join(os.path.dirname(__file__), "coverage"))
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
        fst = os.stat(script_path)
        os.chmod(script_path, fst.st_mode | stat.S_IEXEC)

    log.info("Returning script path %r", script_path)
    return script_path
