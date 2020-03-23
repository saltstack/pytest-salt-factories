# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import shutil

import pytest

from saltfactories.utils.processes.sshd import SshdDaemon


@pytest.fixture(scope="module")
def sshd_config_dir(salt_factories):
    config_dir = salt_factories.root_dir.join("sshd").ensure(dir=True)
    yield config_dir.strpath
    shutil.rmtree(config_dir.strpath, ignore_errors=True)


@pytest.fixture(scope="module")
def sshd(request, sshd_config_dir, salt_factories):
    return salt_factories.spawn_daemon(
        request, "sshd", SshdDaemon, "test-sshd", config_dir=sshd_config_dir, cwd=sshd_config_dir
    )


@pytest.mark.skip_on_windows
@pytest.mark.skip_if_binaries_missing("sshd", "ssh-keygen")
def test_sshd(sshd):
    assert sshd.is_alive()
