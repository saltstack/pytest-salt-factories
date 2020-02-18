# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import functools
import logging
import os
import stat
import tempfile
import textwrap

import pytest
import salt.version

log = logging.getLogger(__name__)

pytest_plugins = ["pytester"]


def pytest_report_header():
    return "salt-version: {}".format(salt.version.__version__)


class Tempfiles:
    """
    Class which generates temporary files and cleans them when done
    """

    def __init__(self, request):
        self.request = request

    def makepyfile(self, contents, prefix=None, executable=False):
        """
        Creates a python file and returns it's path
        """
        tfile = tempfile.NamedTemporaryFile("w", prefix=prefix or "tmp", suffix=".py", delete=False)
        tfile.write(textwrap.dedent(contents.lstrip("\n")).strip())
        tfile.close()
        if executable is True:
            st = os.stat(tfile.name)
            os.chmod(tfile.name, st.st_mode | stat.S_IEXEC)
        self.request.addfinalizer(functools.partial(self._delete_temp_file, tfile.name))
        with open(tfile.name, "r") as rfh:
            log.debug(
                "Created python file with contents:\n>>>>> %s >>>>>\n%s\n<<<<< %s <<<<<\n",
                tfile.name,
                rfh.read(),
                tfile.name,
            )
        return tfile.name

    def makeslsfile(self, contents, name=None):
        """
        Creates an sls file and returns it's path
        """
        if name is None:
            tfile = tempfile.NamedTemporaryFile("w", suffix=".sls", delete=False)
            name = tfile.name
        with open(name, "w") as wfh:
            wfh.write(textwrap.dedent(contents.lstrip("\n")).strip())
        self.request.addfinalizer(functools.partial(self._delete_temp_file, name))
        with open(name, "r") as rfh:
            log.debug(
                "Created SLS file with contents:\n>>>>> %s >>>>>\n%s\n<<<<< %s <<<<<\n",
                name,
                rfh.read(),
                name,
            )
        return name

    def _delete_temp_file(self, fpath):
        """
        Cleanup the temporary path
        """
        if os.path.exists(fpath):
            os.unlink(fpath)


@pytest.fixture
def tempfiles(request):
    """
    Temporary files fixture
    """
    return Tempfiles(request)
