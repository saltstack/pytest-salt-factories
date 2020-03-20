# -*- coding: utf-8 -*-
"""
tests.utils.test_cli_scripts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test saltfactories.utils.cli_scripts
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import os
import sys
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
        #!{}

        from __future__ import absolute_import
        import os
        import sys

        # We really do not want buffered output
        os.environ[str("PYTHONUNBUFFERED")] = str("1")
        # Don't write .pyc files or create them in __pycache__ directories
        os.environ[str("PYTHONDONTWRITEBYTECODE")] = str("1")

        import atexit
        from salt.scripts import salt_foobar
        import salt.utils.platform

        def main():
            if salt.utils.platform.is_windows():
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
            sys.stdout.flush()
            sys.stderr.flush()
            atexit._run_exitfuncs()
            os._exit(exitcode)
        """.format(
            sys.executable
        )
    )
    assert contents == expected


def test_generate_script_executable(tmpdir):
    """
    Test custom executable path
    """
    script_path = cli_scripts.generate_script(
        tmpdir.strpath, "salt-foobar", executable="/usr/bin/python4"
    )
    with open(script_path) as rfh:
        contents = rfh.read()

    expected = textwrap.dedent(
        """\
        #!/usr/bin/python4

        from __future__ import absolute_import
        import os
        import sys

        # We really do not want buffered output
        os.environ[str("PYTHONUNBUFFERED")] = str("1")
        # Don't write .pyc files or create them in __pycache__ directories
        os.environ[str("PYTHONDONTWRITEBYTECODE")] = str("1")

        import atexit
        from salt.scripts import salt_foobar
        import salt.utils.platform

        def main():
            if salt.utils.platform.is_windows():
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
            sys.stdout.flush()
            sys.stderr.flush()
            atexit._run_exitfuncs()
            os._exit(exitcode)
        """
    )
    assert contents == expected


def test_generate_script_long_executable(tmpdir):
    """
    Test that long executable paths get converted to `/usr/bin/env python`
    """
    executable = sys.executable
    while len(executable) <= 128:
        executable += executable

    script_path = cli_scripts.generate_script(tmpdir.strpath, "salt-foobar", executable=executable)
    with open(script_path) as rfh:
        contents = rfh.read()

    expected = textwrap.dedent(
        """\
        #!/usr/bin/env python

        from __future__ import absolute_import
        import os
        import sys

        # We really do not want buffered output
        os.environ[str("PYTHONUNBUFFERED")] = str("1")
        # Don't write .pyc files or create them in __pycache__ directories
        os.environ[str("PYTHONDONTWRITEBYTECODE")] = str("1")

        import atexit
        from salt.scripts import salt_foobar
        import salt.utils.platform

        def main():
            if salt.utils.platform.is_windows():
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
        #!{}

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
        from salt.scripts import salt_foobar
        import salt.utils.platform

        def main():
            if salt.utils.platform.is_windows():
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
            sys.stdout.flush()
            sys.stderr.flush()
            atexit._run_exitfuncs()
            os._exit(exitcode)
        """.format(
            sys.executable, code_dir
        )
    )
    assert contents == expected


def test_generate_script_inject_coverage(tmpdir):
    """
    Test coverage related code included in script generation
    """
    # If code_dir is not passed, assert that we fail
    with pytest.raises(RuntimeError):
        cli_scripts.generate_script(tmpdir.strpath, "salt-foobar-fail", inject_coverage=True)

    code_dir = tmpdir.mkdir("code-dir").strpath
    script_path = cli_scripts.generate_script(
        tmpdir.strpath, "salt-foobar", code_dir=code_dir, inject_coverage=True
    )
    with open(script_path) as rfh:
        contents = rfh.read()

    expected = textwrap.dedent(
        """\
        #!{}

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
        from salt.scripts import salt_foobar
        import salt.utils.platform

        def main():
            if salt.utils.platform.is_windows():
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
            sys.stdout.flush()
            sys.stderr.flush()
            atexit._run_exitfuncs()
            os._exit(exitcode)
        """.format(
            sys.executable, code_dir
        )
    )
    assert contents == expected


def test_generate_script_inject_sitecustomize(tmpdir):
    """
    Test sitecustomize injection related code included in script generation
    """
    sitecustomize_path = os.path.join(os.path.dirname(cli_scripts.__file__), "coverage")
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
        #!{}

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
        from salt.scripts import salt_foobar
        import salt.utils.platform

        def main():
            if salt.utils.platform.is_windows():
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
            sys.stdout.flush()
            sys.stderr.flush()
            atexit._run_exitfuncs()
            os._exit(exitcode)
        """.format(
            sys.executable, code_dir, sitecustomize_path
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
        #!{}

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
        from salt.scripts import salt_foobar_2
        import salt.utils.platform

        def main():
            if salt.utils.platform.is_windows():
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
            sys.stdout.flush()
            sys.stderr.flush()
            atexit._run_exitfuncs()
            os._exit(exitcode)
        """.format(
            sys.executable, sitecustomize_path
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
        #!{}

        from __future__ import absolute_import
        import os
        import sys

        # We really do not want buffered output
        os.environ[str("PYTHONUNBUFFERED")] = str("1")
        # Don't write .pyc files or create them in __pycache__ directories
        os.environ[str("PYTHONDONTWRITEBYTECODE")] = str("1")

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
        """.format(
            sys.executable
        )
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
        #!{}

        from __future__ import absolute_import
        import os
        import sys

        # We really do not want buffered output
        os.environ[str("PYTHONUNBUFFERED")] = str("1")
        # Don't write .pyc files or create them in __pycache__ directories
        os.environ[str("PYTHONDONTWRITEBYTECODE")] = str("1")

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
        """.format(
            sys.executable
        )
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
        #!{}

        from __future__ import absolute_import
        import os
        import sys

        # We really do not want buffered output
        os.environ[str("PYTHONUNBUFFERED")] = str("1")
        # Don't write .pyc files or create them in __pycache__ directories
        os.environ[str("PYTHONDONTWRITEBYTECODE")] = str("1")

        import atexit
        from salt.scripts import salt_foobar
        import salt.utils.platform

        def main():
            if salt.utils.platform.is_windows():
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
            sys.stdout.flush()
            sys.stderr.flush()
            atexit._run_exitfuncs()
            os._exit(exitcode)
        """.format(
            sys.executable
        )
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
        #!{}

        from __future__ import absolute_import
        import os
        import sys

        # We really do not want buffered output
        os.environ[str("PYTHONUNBUFFERED")] = str("1")
        # Don't write .pyc files or create them in __pycache__ directories
        os.environ[str("PYTHONDONTWRITEBYTECODE")] = str("1")

        import atexit
        from salt.scripts import salt_foobar
        import salt.utils.platform

        def main():
            if salt.utils.platform.is_windows():
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
            sys.stdout.flush()
            sys.stderr.flush()
            atexit._run_exitfuncs()
            os._exit(exitcode)
        """.format(
            sys.executable
        )
    )
    assert contents == expected
    statinfo_1 = os.stat(script_path)

    script_path = cli_scripts.generate_script(tmpdir.strpath, "salt-foobar")
    with open(script_path) as rfh:
        contents = rfh.read()
    assert contents == expected
    statinfo_2 = os.stat(script_path)

    assert statinfo_1 == statinfo_2
