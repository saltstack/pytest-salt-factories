# -*- coding: utf-8 -*-

# Import Python libs
import os

# Import 3rd-party libs
import nox

# Nox options
#  Reuse existing virtualenvs
nox.options.reuse_existing_virtualenvs = True
#  Don't fail on missing interpreters
nox.options.error_on_missing_interpreters = False

COVERAGE_VERSION_REQUIREMENT = 'coverage==4.5.4'
SALT_REQUIREMENT = os.environ.get('SALT_REQUIREMENT') or 'salt'


@nox.session(python=('2', '3.5', '3.6', '3.7'))
def tests(session):
    '''
    Run tests
    '''
    session.install('-r', 'requirements.txt', silent=False)
    session.install(COVERAGE_VERSION_REQUIREMENT, SALT_REQUIREMENT)
    session.run('coverage', 'erase')
    tests = session.posargs or ['tests/']
    session.run('coverage', 'run', '-m', 'py.test', '-ra', *tests)
    session.notify('coverage')


@nox.session
def coverage(session):
    '''
    Coverage analysis.
    '''
    session.install(COVERAGE_VERSION_REQUIREMENT)
    session.run('coverage', 'report', '--fail-under=100', '--show-missing')
    session.run('coverage', 'erase')
