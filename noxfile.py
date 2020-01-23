# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import sys
import tempfile

# Import 3rd-party libs
import nox
from nox.command import CommandFailed
from nox.virtualenv import VirtualEnv

IS_PY3 = sys.version_info > (2,)
COVERAGE_VERSION_REQUIREMENT = 'coverage==4.5.4'
SALT_REQUIREMENT = os.environ.get('SALT_REQUIREMENT') or 'salt>=2019.2.0'
USE_SYSTEM_PYTHON = 'USE_SYSTEM_PYTHON' in os.environ

# Be verbose when runing under a CI context
PIP_INSTALL_SILENT = (
    os.environ.get('JENKINS_URL')
    or os.environ.get('CI')
    or os.environ.get('DRONE')
    or os.environ.get('GITHUB_ACTIONS')
) is None

# Nox options
#  Reuse existing virtualenvs
nox.options.reuse_existing_virtualenvs = True
#  Don't fail on missing interpreters
nox.options.error_on_missing_interpreters = False


def _patch_session(session):
    if USE_SYSTEM_PYTHON is False:
        session.log('NOT Patching nox to install against the system python')
        return

    session.log('Patching nox to install against the system python')
    # Let's get sys.prefix
    sys_prefix = session.run(
        'python',
        '-c' 'import sys; sys.stdout.write("{}".format(sys.prefix))',
        silent=True,
        log=False,
    )
    # Let's patch nox to make it run and in partcular, install, to the system python
    session._runner.venv = VirtualEnv(
        sys_prefix, interpreter=session._runner.func.python, reuse_existing=True,
    )


@nox.session(python=('2', '2.7', '3.5', '3.6', '3.7'))
def tests(session):
    '''
    Run tests
    '''
    _patch_session(session)
    session.install('-r', 'requirements-testing.txt', silent=PIP_INSTALL_SILENT)
    session.install(COVERAGE_VERSION_REQUIREMENT, SALT_REQUIREMENT)
    session.install('.')
    session.run('coverage', 'erase')
    tests = session.posargs or ['tests/']
    session.run('coverage', 'run', '-m', 'py.test', '-ra', *tests)
    session.notify('coverage')


@nox.session
def coverage(session):
    '''
    Coverage analysis.
    '''
    _patch_session(session)
    session.install(COVERAGE_VERSION_REQUIREMENT)
    session.run('coverage', 'xml', '-o', 'coverage.xml')
    session.run('coverage', 'report', '--fail-under=80', '--show-missing')
    session.run('coverage', 'erase')


@nox.session(python='3.7')
def blacken(session):
    '''
    Run black code formater.
    '''
    _patch_session(session)
    session.install(
        '--progress-bar=off', '-r', 'requirements-testing.txt', silent=PIP_INSTALL_SILENT
    )
    files = ['saltfactories', 'tests', 'noxfile.py', 'setup.py']
    session.run('sq-black', '-l 100', '--exclude=saltfactories/_version.py', *files)
    session.run(
        'isort',
        '-y',
        '--recursive',
        '-a',
        'from __future__ import absolute_import, print_function, unicode_literals',
    )


def _lint(session, rcfile, flags, paths):
    _patch_session(session)
    session.install(
        '--progress-bar=off', '-r', 'requirements-testing.txt', silent=PIP_INSTALL_SILENT
    )
    session.run('pylint', '--version')
    pylint_report_path = os.environ.get('PYLINT_REPORT')

    cmd_args = ['pylint', '--rcfile={}'.format(rcfile)] + list(flags) + list(paths)

    stdout = tempfile.TemporaryFile(mode='w+b')
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
                contents = contents.decode('utf-8')
            else:
                contents = contents.encode('utf-8')
            sys.stdout.write(contents)
            sys.stdout.flush()
            if pylint_report_path:
                # Write report
                with open(pylint_report_path, 'w') as wfh:
                    wfh.write(contents)
                session.log('Report file written to %r', pylint_report_path)
        stdout.close()


@nox.session(python='3.5')
def lint(session):
    '''
    Run PyLint against Salt and it's test suite. Set PYLINT_REPORT to a path to capture output.
    '''
    session.notify('lint-code-{}'.format(session.python))
    session.notify('lint-tests-{}'.format(session.python))


@nox.session(python='3.5', name='lint-code')
def lint_code(session):
    '''
    Run PyLint against the code. Set PYLINT_REPORT to a path to capture output.
    '''
    flags = ['--disable=I']
    if session.posargs:
        paths = session.posargs
    else:
        paths = ['setup.py', 'noxfile.py', 'saltfactories/']
    _lint(session, '.pylintrc', flags, paths)


@nox.session(python='3.5', name='lint-tests')
def lint_tests(session):
    '''
    Run PyLint against Salt and it's test suite. Set PYLINT_REPORT to a path to capture output.
    '''
    flags = ['--disable=I']
    if session.posargs:
        paths = session.posargs
    else:
        paths = ['tests/']
    _lint(session, '.pylintrc', flags, paths)
