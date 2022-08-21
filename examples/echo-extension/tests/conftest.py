import os

import pytest

from echoext import PACKAGE_ROOT
from saltfactories.utils import random_string


@pytest.fixture(scope="session")
def salt_factories_config():
    """
    Return a dictionary with the keyword arguments for FactoriesManager
    """
    coverage_rc_path = os.environ.get("COVERAGE_PROCESS_START")
    if coverage_rc_path:
        coverage_db_path = PACKAGE_ROOT / ".coverage"
    else:
        coverage_db_path = None
    return {
        "code_dir": str(PACKAGE_ROOT),
        "coverage_rc_path": coverage_rc_path,
        "coverage_db_path": coverage_db_path,
        "inject_sitecustomize": "COVERAGE_PROCESS_START" in os.environ,
        "start_timeout": 120 if os.environ.get("CI") else 60,
    }


@pytest.fixture(scope="package")
def master(salt_factories):
    return salt_factories.salt_master_daemon(random_string("master-"))


@pytest.fixture(scope="package")
def minion(master):
    return master.salt_minion_daemon(random_string("minion-"))
