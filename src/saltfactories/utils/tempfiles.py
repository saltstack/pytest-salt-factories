"""
Temporary files helpers.

..
    PYTEST_DONT_REWRITE
"""
import logging
import os
import pathlib
import shutil
import tempfile
import textwrap
from contextlib import contextmanager

import attr

log = logging.getLogger(__name__)


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
            if str(created_directory) == str(basepath):
                break
            if not any(created_directory.iterdir()):
                shutil.rmtree(str(created_directory), ignore_errors=True)
                log.debug("Deleted temp directory: %s", created_directory)
            else:
                log.debug("Not deleting %s because it's not empty", created_directory)
            created_directory = created_directory.parent


@contextmanager
def temp_file(name=None, contents=None, directory=None, strip_first_newline=True):
    """
    Create a temporary file as a context manager.

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

            assert temp_path.is_file() is False

    Or, it can be used as a pytest helper function:

    .. code-block:: python

        import pytest


        def test_blah():
            with pytest.helpers.temp_file("blah.txt") as temp_path:
                assert temp_path.is_file()

            assert temp_path.is_file() is False

    To create files under a sub-directory, one has two choices:

    .. code-block:: python

        import pytest


        def test_relative_subdirectory():
            with pytest.helpers.temp_file("foo/blah.txt") as temp_path:
                assert temp_path.is_file()
                assert temp_path.parent.is_dir()
                assert temp_path.parent.name == "foo"

            assert not temp_path.is_file() is False
            assert not temp_path.parent.is_dir() is False


    .. code-block:: python

        import os
        import pytest
        import tempfile

        ROOT_DIR = tempfile.gettempdir()


        def test_absolute_subdirectory_1():
            destpath = os.path.join(ROOT_DIR, "foo")
            with pytest.helpers.temp_file("blah.txt", directory=destpath) as temp_path:
                assert temp_path.is_file()
                assert temp_path.parent.is_dir()
                assert temp_path.parent.name == "foo"

            assert not temp_path.is_file() is False
            assert not temp_path.parent.is_dir() is False


        def test_absolute_subdirectory_2():
            destpath = os.path.join(ROOT_DIR, "foo", "blah.txt")
            with pytest.helpers.temp_file(destpath) as temp_path:
                assert temp_path.is_file()
                assert temp_path.parent.is_dir()
                assert temp_path.parent.name == "foo"

            assert temp_path.is_file() is False
            assert temp_path.parent.is_dir() is False

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


@attr.s(kw_only=True, slots=True)
class SaltEnv:
    """
    This helper class represent a Salt Environment, either for states or pillar.

    It's base purpose it to handle temporary file creation/deletion during testing.

    :keyword str name:
        The salt environment name, commonly, 'base' or 'prod'
    :keyword list paths:
        The salt environment list of paths.

        .. admonition:: Note

            The first entry in this list, is the path that will get used to create temporary files in,
            ie, the return value of the :py:attr:`saltfactories.utils.tempfiles.SaltEnv.write_path`
            attribute.
    """

    name = attr.ib()
    paths = attr.ib(default=attr.Factory(list))

    def __attrs_post_init__(self):
        """
        Post attrs initialization routines.
        """
        for idx, path in enumerate(self.paths[:]):
            if not isinstance(path, pathlib.Path):
                # We have to cast path to a string because on Py3.5, path might be an instance of pathlib2.Path
                path = pathlib.Path(str(path))
                self.paths[idx] = path
            path.mkdir(parents=True, exist_ok=True)

    @property
    def write_path(self):
        """
        The path where temporary files are created.
        """
        return self.paths[0]

    def temp_file(self, name, contents=None, strip_first_newline=True):
        """
        Create a temporary file within this saltenv.

        Please check :py:func:`saltfactories.utils.tempfiles.temp_file` for documentation.
        """
        return temp_file(
            name=name,
            contents=contents,
            directory=self.write_path,
            strip_first_newline=strip_first_newline,
        )

    def as_dict(self):
        """
        Returns a dictionary of the right types to update the salt configuration.

        :return dict:
        """
        return {self.name: [str(p) for p in self.paths]}


@attr.s(kw_only=True)
class SaltEnvs:
    """
    This class serves as a container for multiple salt environments for states or pillar.

    :keyword dict envs:
        The `envs` dictionary should be a mapping of a string as key, the `saltenv`, commonly 'base' or 'prod',
        and the value an instance of :py:class:`~saltfactories.utils.tempfiles.SaltEnv` or a list of strings(paths).
        In the case where a list of strings(paths) is passed, it is converted to an instance of
        :py:class:`~saltfactories.utils.tempfiles.SaltEnv`

    To provide a better user experience, the salt environments can be accessed as attributes of this class.

    .. code-block:: python

        envs = SaltEnvs(
            {
                "base": [
                    "/path/to/base/env",
                ],
                "prod": [
                    "/path/to/prod/env",
                ],
            }
        )
        with envs.base.temp_file("foo.txt", "foo contents") as base_foo_path:
            ...
        with envs.prod.temp_file("foo.txt", "foo contents") as prod_foo_path:
            ...

    """

    envs = attr.ib()

    def __attrs_post_init__(self):
        """
        Post attrs initialization routines.
        """
        for envname, envtree in self.envs.items():
            if not isinstance(envtree, SaltEnv):
                if isinstance(envtree, str):
                    envtree = [envtree]
                self.envs[envname] = SaltEnv(name=envname, paths=envtree)
            setattr(self, envname, self.envs[envname])

    def as_dict(self):
        """
        Returns a dictionary of the right types to update the salt configuration.

        :return dict:
        """
        config = {}
        for env in self.envs.values():
            config.update(env.as_dict())
        return config


@attr.s(kw_only=True)
class SaltStateTree(SaltEnvs):
    """
    Helper class which handles temporary file creation within the state tree.

    :keyword dict envs:
        A mapping of a ``saltenv`` to a list of paths.

        .. code-block:: python

            envs = {
                "base": [
                    "/path/to/base/env",
                    "/another/path/to/base/env",
                ],
                "prod": [
                    "/path/to/prod/env",
                    "/another/path/to/prod/env",
                ],
            }

    The state tree environments can be accessed by attribute:

    .. code-block:: python

        # See example of envs definition above
        state_tree = SaltStateTree(envs=envs)

        # To access the base saltenv
        base = state_tree.envs["base"]

        # Alternatively, in a simpler form
        base = state_tree.base

    When setting up the Salt configuration to use an instance of
    :py:class:`~saltfactories.utils.tempfiles.SaltStateTree`, the following pseudo code can be followed.

    .. code-block:: python

        # Using the state_tree defined above:
        salt_config = {
            # ... other salt config entries ...
            "file_roots": state_tree.as_dict()
            # ... other salt config entries ...
        }

    .. admonition:: Attention

        The temporary files created by the :py:meth:`~saltfactories.utils.tempfiles.SaltStateTree.temp_file`
        are written to the first path passed when instantiating the ``SaltStateTree``, ie, the return value
        of the :py:attr:`saltfactories.utils.tempfiles.SaltStateTree.write_path` attribute.

        .. code-block:: python

            # Given the example mapping shown above ...

            with state_tree.base.temp_file("foo.sls") as path:
                assert str(path) == "/path/to/base/env/foo.sls"
    """


@attr.s(kw_only=True)
class SaltPillarTree(SaltEnvs):
    """
    Helper class which handles temporary file creation within the pillar tree.

    :keyword dict envs:
        A mapping of a ``saltenv`` to a list of paths.

        .. code-block:: python

            envs = {
                "base": [
                    "/path/to/base/env",
                    "/another/path/to/base/env",
                ],
                "prod": [
                    "/path/to/prod/env",
                    "/another/path/to/prod/env",
                ],
            }

    The pillar tree environments can be accessed by attribute:

    .. code-block:: python

        # See example of envs definition above
        pillar_tree = SaltPillarTree(envs=envs)

        # To access the base saltenv
        base = pillar_tree.envs["base"]

        # Alternatively, in a simpler form
        base = pillar_tree.base

    When setting up the Salt configuration to use an instance of
    :py:class:`~saltfactories.utils.tempfiles.SaltPillarTree`, the following pseudo code can be followed.

    .. code-block:: python

        # Using the pillar_tree defined above:
        salt_config = {
            # ... other salt config entries ...
            "pillar_roots": pillar_tree.as_dict()
            # ... other salt config entries ...
        }

    .. admonition:: Attention

        The temporary files created by the :py:meth:`~saltfactories.utils.tempfiles.SaltPillarTree.temp_file`
        are written to the first path passed when instantiating the ``SaltPillarTree``, ie, the return value
        of the :py:attr:`saltfactories.utils.tempfiles.SaltPillarTree.write_path` attribute.

        .. code-block:: python

            # Given the example mapping shown above ...

            with state_tree.base.temp_file("foo.sls") as path:
                assert str(path) == "/path/to/base/env/foo.sls"
    """
