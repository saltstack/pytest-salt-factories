import pathlib
import shutil
import tempfile

import pytest

from saltfactories.utils import tempfiles


@pytest.mark.parametrize("name", ["foo", "foo/bar"])
def test_temp_directory_with_name(name):
    try:
        expected_path = pathlib.Path(tempfile.gettempdir()) / name
        assert expected_path.is_dir() is False
        with tempfiles.temp_directory(name=name) as tpath:
            assert tpath.is_dir()
            assert tpath == expected_path
        assert expected_path.is_dir() is False
    finally:
        shutil.rmtree(str(expected_path), ignore_errors=True)


def test_temp_directory_without_name():
    try:
        expected_parent_path = pathlib.Path(tempfile.gettempdir())
        with tempfiles.temp_directory() as tpath:
            assert tpath.is_dir()
            assert tpath.parent == expected_parent_path
        assert tpath.is_dir() is False
    finally:
        shutil.rmtree(str(tpath), ignore_errors=True)


def test_temp_directory_with_basepath(tmp_path):
    with tempfiles.temp_directory(basepath=tmp_path) as tpath:
        assert tpath.is_dir()
        assert str(tpath.parent) == str(tmp_path)
    assert tpath.is_dir() is False
    assert tmp_path.is_dir() is True


@pytest.mark.parametrize("name", ["foo.txt", "foo/bar.txt"])
def test_temp_file_with_name(tmp_path, name):
    expected_path = tmp_path / name
    assert expected_path.is_file() is False
    with tempfiles.temp_file(name=name, directory=tmp_path) as tpath:
        assert tpath.is_file()
        assert str(tpath) == str(expected_path)
    assert expected_path.is_file() is False


def test_temp_file_without_name(tmp_path):
    expected_parent_path = tmp_path
    with tempfiles.temp_file(directory=tmp_path) as tpath:
        assert tpath.is_file()
        assert str(tpath.parent) == str(expected_parent_path)
    assert tpath.is_file() is False


@pytest.mark.parametrize("name", ["foo.txt", "foo/bar.txt"])
def test_temp_file_with_name_no_directory(name):
    try:
        expected_path = pathlib.Path(tempfile.gettempdir()) / name
        assert expected_path.is_file() is False
        with tempfiles.temp_file(name=name) as tpath:
            assert tpath.is_file()
            assert str(tpath) == str(expected_path)
        assert expected_path.is_file() is False
    finally:
        shutil.rmtree(str(expected_path), ignore_errors=True)


def test_temp_file_without_name_no_directory():
    try:
        expected_parent_path = pathlib.Path(tempfile.gettempdir())
        with tempfiles.temp_file() as tpath:
            assert tpath.is_file()
            assert str(tpath.parent) == str(expected_parent_path)
        assert tpath.is_file() is False
    finally:
        shutil.rmtree(str(tpath), ignore_errors=True)


def test_temp_file_does_not_delete_non_empty_directories(tmp_path):
    expected_parent_path = tmp_path
    level1_path = expected_parent_path / "level1"
    level2_path = level1_path / "level2"
    assert not level1_path.is_dir()
    assert not level2_path.is_dir()
    with tempfiles.temp_file("level1/foo.txt", directory=expected_parent_path) as tpath1:
        assert tpath1.is_file()
        assert level1_path.is_dir()
        assert not level2_path.is_dir()
        with tempfiles.temp_file("level1/level2/foo.txt", directory=expected_parent_path) as tpath2:
            assert tpath2.is_file()
            assert level1_path.is_dir()
            assert level2_path.is_dir()
        assert not tpath2.is_file()
        assert not level2_path.is_dir()
        assert tpath1.is_file()
        assert level1_path.is_dir()
    assert not level1_path.is_dir()
    assert not level2_path.is_dir()


@pytest.mark.parametrize("strip_first_newline", [True, False])
def test_temp_file_contents(strip_first_newline):
    contents = """
     These are the contents, first line
      Second line
    """
    if strip_first_newline:
        expected_contents = "These are the contents, first line\n Second line\n"
    else:
        expected_contents = "\nThese are the contents, first line\n Second line\n"
    with tempfiles.temp_file(contents=contents, strip_first_newline=strip_first_newline) as tpath:
        assert tpath.is_file()
        assert tpath.read_text() == expected_contents


def test_saltenvs_temp_file(tmp_path):
    with tempfiles.temp_directory("state-tree", basepath=tmp_path) as state_tree_path:
        with tempfiles.temp_directory(
            "base1", basepath=state_tree_path
        ) as base_env_path_1, tempfiles.temp_directory(
            "base2", basepath=state_tree_path
        ) as base_env_path_2:
            saltenv = tempfiles.SaltEnvs(envs={"base": [base_env_path_1, base_env_path_2]})

            # Let's make sure we can access the saltenv by attribute
            assert saltenv.base == saltenv.envs["base"]

            # Let's create a temporary file using the `temp_file` helper method
            top_file_contents = """
            'base':
              '*':
                - bar
            """
            with saltenv.base.temp_file("top.sls", contents=top_file_contents) as top_file_path:
                with pytest.raises(ValueError):
                    # the top file shall not be created within the base_env_path_2
                    # We have to cast to a string because on Py3.5, the path might be an instance of pathlib2.Path
                    top_file_path.relative_to(str(base_env_path_2))

                # It should however, be created within the base_env_path_1
                # We have to cast to a string because on Py3.5, the path might be an instance of pathlib2.Path
                relpath = top_file_path.relative_to(str(base_env_path_1))
                assert relpath


@pytest.mark.parametrize(
    "klass",
    (
        tempfiles.SaltEnvs,
        tempfiles.SaltPillarTree,
        tempfiles.SaltStateTree,
    ),
)
def test_saltenvs_as_dict(tmp_path, klass):
    with tempfiles.temp_directory("tree", basepath=tmp_path) as tree_path:
        with tempfiles.temp_directory(
            "base1", basepath=tree_path
        ) as base_env_path_1, tempfiles.temp_directory(
            "base2", basepath=tree_path
        ) as base_env_path_2, tempfiles.temp_directory(
            "prod1", basepath=tree_path
        ) as prod_env_path_1, tempfiles.temp_directory(
            "prod2", basepath=tree_path
        ) as prod_env_path_2:
            envs = klass(
                envs={
                    "base": [base_env_path_1, base_env_path_2],
                    "prod": [prod_env_path_1, prod_env_path_2],
                }
            )
            config = envs.as_dict()
            assert isinstance(config, dict)
            for envname, paths in config.items():
                assert isinstance(envname, str)
                for path in paths:
                    assert isinstance(path, str)
