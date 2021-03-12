"""
    tests.functional.markers.test_requires_salt_modules
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the ``@pytest.mark.requires_salt_modules`` marker
"""


def test_has_required_salt_module(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.requires_salt_modules("cmd")
        def test_one():
            assert True
        """
    )
    res = testdir.runpytest_inprocess()
    res.assert_outcomes(passed=1)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")


def test_missing_required_salt_module(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.requires_salt_modules("cmdmod")
        def test_one():
            assert True
        """
    )
    res = testdir.runpytest_inprocess()
    res.assert_outcomes(skipped=1)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")


def test_has_required_custom_salt_module(testdir):
    testdir.makepyfile(
        r"""
        import pathlib
        import textwrap
        import pytest
        import logging
        import saltfactories.utils.functional

        log = logging.getLogger(__name__)

        custom_module_name = "bogus"


        @pytest.fixture(scope="session")
        def session_markers_loader(salt_factories):
            minion_id = "session-markers-loader-modules"
            root_dir = salt_factories.get_root_dir_for_daemon(minion_id)
            rootfs = root_dir / "rootfs" / "states"
            rootfs.mkdir(parents=True)
            rootfs_modules = rootfs / "_modules"
            rootfs_modules.mkdir(parents=True)
            module_contents = textwrap.dedent('''\
            def echo(text):
                return text
            ''')
            module_path = rootfs_modules / "{}.py".format(custom_module_name)
            module_path.write_text(module_contents)
            config_defaults = {
                "root_dir": str(root_dir),
            }
            config_overrides = {
                "file_client": "local",
                "features": {"enable_slsvars_fixes": True},
                "file_roots": {
                    "base": [str(rootfs)]
                }
            }
            factory = salt_factories.get_salt_minion_daemon(
                minion_id, config_defaults=config_defaults, config_overrides=config_overrides,
            )
            loader_instance = saltfactories.utils.functional.Loaders(factory.config.copy())
            assert loader_instance.modules.bogus.echo("foo") == "foo"
            return loader_instance

        @pytest.mark.requires_salt_modules(custom_module_name)
        def test_custom_module():
            assert True
        """
    )
    res = testdir.runpytest_inprocess()
    res.assert_outcomes(passed=1)
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")
