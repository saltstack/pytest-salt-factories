import pytest
from pytestskipmarkers.utils import platform


@pytest.fixture
def salt_cli_timeout():
    if platform.is_spawning_platform():
        return 30
    return None
