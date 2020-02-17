# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import pytest


@pytest.fixture(scope="module")
def master(request, salt_factories):
    return salt_factories.spawn_master(request, "master-1")


@pytest.fixture
def salt_run(request, salt_factories, master):
    return salt_factories.get_salt_run(request, master.config["id"])


def test_master(master):
    assert master.is_alive()


def test_salt_run(master, salt_run):
    max_open_files_config_value = master.config["max_open_files"]
    ret = salt_run.run("config.get", "max_open_files")
    assert ret.exitcode == 0, ret
    assert ret.json == max_open_files_config_value
