"""
Test saltfactories.utils.cli_scripts.
"""
import os
import pathlib
import textwrap

import pytest

import saltfactories.utils.cli_scripts as cli_scripts


def test_generate_script_defaults(tmpdir):
    """
    Test defaults script generation
    """
    script_path = cli_scripts.generate_script(tmpdir.strpath, "salt-foobar")
    with open(script_path) as rfh:
        contents = rfh.read()

    expected = textwrap.dedent(
        """\
        from __future__ import absolute_import
        import os
        import sys

        # We really do not want buffered output
        os.environ[str("PYTHONUNBUFFERED")] = str("1")
        # Don't write .pyc files or create them in __pycache__ directories
        os.environ[str("PYTHONDONTWRITEBYTECODE")] = str("1")

        import atexit
        import traceback
        from salt.scripts import salt_foobar

        def main():
            if sys.platform.startswith("win"):
                import os.path
                import py_compile
                cfile = os.path.splitext(__file__)[0] + '.pyc'
                if not os.path.exists(cfile):
                    py_compile.compile(__file__, cfile)
            salt_foobar()

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
    )
    assert contents == expected


def test_generate_script_code_dir(tmpdir):
    """
    Test code_dir inclusion in script generation
    """
    code_dir = tmpdir.mkdir("code-dir").strpath
    script_path = cli_scripts.generate_script(tmpdir.strpath, "salt-foobar", code_dir=code_dir)
    with open(script_path) as rfh:
        contents = rfh.read()

    expected = textwrap.dedent(
        """\
        from __future__ import absolute_import
        import os
        import sys

        # We really do not want buffered output
        os.environ[str("PYTHONUNBUFFERED")] = str("1")
        # Don't write .pyc files or create them in __pycache__ directories
        os.environ[str("PYTHONDONTWRITEBYTECODE")] = str("1")

        CODE_DIR = r'{}'
        if CODE_DIR in sys.path:
            sys.path.remove(CODE_DIR)
        sys.path.insert(0, CODE_DIR)

        import atexit
        import traceback
        from salt.scripts import salt_foobar

        def main():
            if sys.platform.startswith("win"):
                import os.path
                import py_compile
                cfile = os.path.splitext(__file__)[0] + '.pyc'
                if not os.path.exists(cfile):
                    py_compile.compile(__file__, cfile)
            salt_foobar()

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
        """.format(
            code_dir
        )
    )
    assert contents == expected


def test_generate_script_inject_coverage(tmpdir):
    """
    Test coverage related code included in script generation
    """
    # If code_dir is not passed, assert that we fail
    with pytest.raises(pytest.UsageError):
        cli_scripts.generate_script(tmpdir.strpath, "salt-foobar-fail", inject_coverage=True)

    code_dir = tmpdir.mkdir("code-dir").strpath
    script_path = cli_scripts.generate_script(
        tmpdir.strpath, "salt-foobar", code_dir=code_dir, inject_coverage=True
    )
    with open(script_path) as rfh:
        contents = rfh.read()

    expected = textwrap.dedent(
        """\
        from __future__ import absolute_import
        import os
        import sys

        # We really do not want buffered output
        os.environ[str("PYTHONUNBUFFERED")] = str("1")
        # Don't write .pyc files or create them in __pycache__ directories
        os.environ[str("PYTHONDONTWRITEBYTECODE")] = str("1")

        CODE_DIR = r'{}'
        if CODE_DIR in sys.path:
            sys.path.remove(CODE_DIR)
        sys.path.insert(0, CODE_DIR)

        # Setup coverage environment variables
        COVERAGE_FILE = os.path.join(CODE_DIR, '.coverage')
        COVERAGE_PROCESS_START = os.path.join(CODE_DIR, '.coveragerc')
        os.environ[str('COVERAGE_FILE')] = str(COVERAGE_FILE)
        os.environ[str('COVERAGE_PROCESS_START')] = str(COVERAGE_PROCESS_START)

        import atexit
        import traceback
        from salt.scripts import salt_foobar

        def main():
            if sys.platform.startswith("win"):
                import os.path
                import py_compile
                cfile = os.path.splitext(__file__)[0] + '.pyc'
                if not os.path.exists(cfile):
                    py_compile.compile(__file__, cfile)
            salt_foobar()

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
        """.format(
            code_dir
        )
    )
    assert contents == expected


def test_generate_script_inject_sitecustomize(tmpdir):
    """
    Test sitecustomize injection related code included in script generation
    """
    sitecustomize_path = pathlib.Path(cli_scripts.__file__).resolve().parent / "coverage"
    code_dir = tmpdir.mkdir("code-dir").strpath
    script_path = cli_scripts.generate_script(
        tmpdir.strpath,
        "salt-foobar",
        code_dir=code_dir,
        inject_coverage=True,
        inject_sitecustomize=True,
    )
    with open(script_path) as rfh:
        contents = rfh.read()

    expected = textwrap.dedent(
        """\
        from __future__ import absolute_import
        import os
        import sys

        # We really do not want buffered output
        os.environ[str("PYTHONUNBUFFERED")] = str("1")
        # Don't write .pyc files or create them in __pycache__ directories
        os.environ[str("PYTHONDONTWRITEBYTECODE")] = str("1")

        CODE_DIR = r'{}'
        if CODE_DIR in sys.path:
            sys.path.remove(CODE_DIR)
        sys.path.insert(0, CODE_DIR)

        # Setup coverage environment variables
        COVERAGE_FILE = os.path.join(CODE_DIR, '.coverage')
        COVERAGE_PROCESS_START = os.path.join(CODE_DIR, '.coveragerc')
        os.environ[str('COVERAGE_FILE')] = str(COVERAGE_FILE)
        os.environ[str('COVERAGE_PROCESS_START')] = str(COVERAGE_PROCESS_START)

        # Allow sitecustomize.py to be importable for test coverage purposes
        SITECUSTOMIZE_DIR = r'{}'
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

        import atexit
        import traceback
        from salt.scripts import salt_foobar

        def main():
            if sys.platform.startswith("win"):
                import os.path
                import py_compile
                cfile = os.path.splitext(__file__)[0] + '.pyc'
                if not os.path.exists(cfile):
                    py_compile.compile(__file__, cfile)
            salt_foobar()

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
        """.format(
            code_dir, str(sitecustomize_path)
        )
    )
    assert contents == expected

    script_path = cli_scripts.generate_script(
        tmpdir.strpath, "salt-foobar-2", inject_sitecustomize=True
    )
    with open(script_path) as rfh:
        contents = rfh.read()

    expected = textwrap.dedent(
        """\
        from __future__ import absolute_import
        import os
        import sys

        # We really do not want buffered output
        os.environ[str("PYTHONUNBUFFERED")] = str("1")
        # Don't write .pyc files or create them in __pycache__ directories
        os.environ[str("PYTHONDONTWRITEBYTECODE")] = str("1")

        # Allow sitecustomize.py to be importable for test coverage purposes
        SITECUSTOMIZE_DIR = r'{}'
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

        import atexit
        import traceback
        from salt.scripts import salt_foobar_2

        def main():
            if sys.platform.startswith("win"):
                import os.path
                import py_compile
                cfile = os.path.splitext(__file__)[0] + '.pyc'
                if not os.path.exists(cfile):
                    py_compile.compile(__file__, cfile)
            salt_foobar_2()

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
        """.format(
            str(sitecustomize_path)
        )
    )
    assert contents == expected


def test_generate_script_salt(tmpdir):
    """
    Test script generation for the salt CLI script
    """
    script_path = cli_scripts.generate_script(tmpdir.strpath, "salt")
    with open(script_path) as rfh:
        contents = rfh.read()

    expected = textwrap.dedent(
        """\
        from __future__ import absolute_import
        import os
        import sys

        # We really do not want buffered output
        os.environ[str("PYTHONUNBUFFERED")] = str("1")
        # Don't write .pyc files or create them in __pycache__ directories
        os.environ[str("PYTHONDONTWRITEBYTECODE")] = str("1")

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
    )
    assert contents == expected


def test_generate_script_salt_api(tmpdir):
    """
    Test script generation for the salt-api CLI script
    """
    script_path = cli_scripts.generate_script(tmpdir.strpath, "salt-api")
    with open(script_path) as rfh:
        contents = rfh.read()

    expected = textwrap.dedent(
        """\
        from __future__ import absolute_import
        import os
        import sys

        # We really do not want buffered output
        os.environ[str("PYTHONUNBUFFERED")] = str("1")
        # Don't write .pyc files or create them in __pycache__ directories
        os.environ[str("PYTHONDONTWRITEBYTECODE")] = str("1")

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
    )
    assert contents == expected


def test_generate_script_creates_missing_bin_dir(tmpdir):
    """
    Test defaults script generation
    """
    script_path = cli_scripts.generate_script(tmpdir.join("blah").strpath, "salt-foobar")
    with open(script_path) as rfh:
        contents = rfh.read()

    expected = textwrap.dedent(
        """\
        from __future__ import absolute_import
        import os
        import sys

        # We really do not want buffered output
        os.environ[str("PYTHONUNBUFFERED")] = str("1")
        # Don't write .pyc files or create them in __pycache__ directories
        os.environ[str("PYTHONDONTWRITEBYTECODE")] = str("1")

        import atexit
        import traceback
        from salt.scripts import salt_foobar

        def main():
            if sys.platform.startswith("win"):
                import os.path
                import py_compile
                cfile = os.path.splitext(__file__)[0] + '.pyc'
                if not os.path.exists(cfile):
                    py_compile.compile(__file__, cfile)
            salt_foobar()

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
    )
    assert contents == expected
    assert os.path.isdir(tmpdir.join("blah").strpath)


def test_generate_script_only_generates_once(tmpdir):
    """
    Test defaults script generation
    """
    script_path = cli_scripts.generate_script(tmpdir.strpath, "salt-foobar")
    with open(script_path) as rfh:
        contents = rfh.read()

    expected = textwrap.dedent(
        """\
        from __future__ import absolute_import
        import os
        import sys

        # We really do not want buffered output
        os.environ[str("PYTHONUNBUFFERED")] = str("1")
        # Don't write .pyc files or create them in __pycache__ directories
        os.environ[str("PYTHONDONTWRITEBYTECODE")] = str("1")

        import atexit
        import traceback
        from salt.scripts import salt_foobar

        def main():
            if sys.platform.startswith("win"):
                import os.path
                import py_compile
                cfile = os.path.splitext(__file__)[0] + '.pyc'
                if not os.path.exists(cfile):
                    py_compile.compile(__file__, cfile)
            salt_foobar()

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
    )
    assert contents == expected
    statinfo_1 = os.stat(script_path)

    script_path = cli_scripts.generate_script(tmpdir.strpath, "salt-foobar")
    with open(script_path) as rfh:
        contents = rfh.read()
    assert contents == expected
    statinfo_2 = os.stat(script_path)

    assert statinfo_1 == statinfo_2
