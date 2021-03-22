"""
saltfactories.utils.tempfiles
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Temporary files utilities
"""
import logging
import os
import pathlib
import shutil
import tempfile
import textwrap
from contextlib import contextmanager

import pytest

log = logging.getLogger(__name__)


@pytest.helpers.register
@contextmanager
def temp_directory(name=None, basepath=None):
    """
    This helper creates a temporary directory.
    It should be used as a context manager which returns the temporary directory path, and, once out of context,
    deletes it.

    :keyword str name:
        The name of the directory to create
    :keyword basepath name:
        The base path of where to create the directory. Defaults to :py:func:`~tempfile.gettempdir`
    :rtype: pathlib.Path

    Can be directly imported and used:

    .. code-block:: python

        from saltfactories.utils.tempfiles import temp_directory


        def test_func():

            with temp_directory() as temp_path:
                assert temp_path.is_dir()

            assert not temp_path.is_dir() is False

    Or, it can be used as a pytest helper function:

    .. code-block:: python

        import pytest


        def test_blah():
            with pytest.helpers.temp_directory() as temp_path:
                assert temp_path.is_dir()

            assert not temp_path.is_dir() is False
    """
    if basepath is None:
        basepath = pathlib.Path(tempfile.gettempdir())
    try:
        if name is not None:
            directory_path = basepath / name
        else:
            directory_path = pathlib.Path(tempfile.mkdtemp(dir=str(basepath)))

        if not directory_path.is_dir():
            directory_path.mkdir(parents=True)
            log.debug("Created temp directory: %s", directory_path)

        yield directory_path
    finally:
        created_directory = directory_path
        while True:
            print(1, basepath, created_directory)
            if str(created_directory) == str(basepath):
                break
            if not any(created_directory.iterdir()):
                shutil.rmtree(str(created_directory), ignore_errors=True)
                log.debug("Deleted temp directory: %s", created_directory)
            else:
                log.debug("Not deleting %s because it's not empty", created_directory)
            created_directory = created_directory.parent


@pytest.helpers.register
@contextmanager
def temp_file(name=None, contents=None, directory=None, strip_first_newline=True):
    """
    This helper creates a temporary file. It should be used as a context manager
    which returns the temporary file path, and, once out of context, deletes it.

    :keyword str name:
        The temporary file name
    :keyword str contents:
        The contents of the temporary file
    :keyword str,pathlib.Path directory:
        The directory where to create the temporary file. Defaults to the value of :py:func:`~tempfile.gettempdir`
    :keyword bool strip_first_newline:
        Either strip the initial first new line char or not.

    :rtype: pathlib.Path

    Can be directly imported and used:

    .. code-block:: python

        from saltfactories.utils.tempfiles import temp_file


        def test_func():

            with temp_file(name="blah.txt") as temp_path:
                assert temp_path.is_file()

            assert not temp_path.is_file() is False

    Or, it can be used as a pytest helper function:

    .. code-block:: python

        import pytest


        def test_blah():
            with pytest.helpers.temp_file("blah.txt") as temp_path:
                assert temp_path.is_file()

            assert not temp_path.is_file() is False
    """
    if directory is None:
        directory = tempfile.gettempdir()

    if not isinstance(directory, pathlib.Path):
        directory = pathlib.Path(str(directory))

    if name is not None:
        file_path = directory / name
    else:
        handle, file_path = tempfile.mkstemp(dir=str(directory))
        os.close(handle)
        file_path = pathlib.Path(file_path)

    # Find out if we were given sub-directories on `name`
    create_directories = file_path.parent.relative_to(directory)

    if create_directories:
        with temp_directory(create_directories, basepath=directory):
            with _write_or_touch(file_path, contents, strip_first_newline=strip_first_newline):
                yield file_path
    else:
        with _write_or_touch(file_path, contents, strip_first_newline=strip_first_newline):
            yield file_path


@contextmanager
def _write_or_touch(file_path, contents, strip_first_newline=True):
    try:
        if contents is not None:
            if contents:
                if contents.startswith("\n") and strip_first_newline:
                    contents = contents[1:]
                file_contents = textwrap.dedent(contents)
            else:
                file_contents = contents

            file_path.write_text(file_contents)
            log_contents = "{0} Contents of {1}\n{2}\n{3} Contents of {1}".format(
                ">" * 6, file_path, file_contents, "<" * 6
            )
            log.debug("Created temp file: %s\n%s", file_path, log_contents)
        else:
            file_path.touch()
            log.debug("Touched temp file: %s", file_path)
        yield
    finally:
        if file_path.exists():
            file_path.unlink()
            log.debug("Deleted temp file: %s", file_path)
