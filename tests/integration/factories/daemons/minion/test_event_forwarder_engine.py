import logging
import time

import pytest
import salt.defaults.events

from saltfactories.utils import random_string

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def master(salt_factories):
    factory = salt_factories.salt_master_daemon(random_string("master-"))
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def minion(master):
    factory = master.salt_minion_daemon(random_string("minion-"))
    with factory.started():
        yield factory


@pytest.fixture
def salt_call_cli(minion):
    return minion.salt_call_cli()


def test_event_listener_engine(minion, salt_call_cli, event_listener):
    """
    There are some events which the minion fires internally that never reach the master.
    We test if we're receiving those
    """
    assert minion.is_running()
    start_time = time.time()
    stop_time = start_time + 120

    ret = salt_call_cli.run("saltutil.refresh_pillar")
    assert ret.returncode == 0, ret

    master_event = None
    expected_tag = salt.defaults.events.MINION_PILLAR_REFRESH_COMPLETE
    master_event_pattern = (minion.id, expected_tag)
    while True:
        if time.time() > stop_time:
            pytest.fail("Failed to receive the refresh pillar event.")

        if not master_event:
            events = event_listener.get_events([master_event_pattern], after_time=start_time)
            for event in events:
                master_event = event
                break

        if master_event:
            # We got all events back
            break

        time.sleep(0.5)

    log.debug("Refresh pillar event received: %s", master_event)
