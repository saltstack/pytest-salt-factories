"""
Test the ``@pytest.mark.requires_salt_modules`` marker.
"""
import pytest


@pytest.mark.parametrize(
    "modules",
    [
        ("cmd",),
        ("cmd", "test"),
    ],
)
def test_has_required_salt_module(pytester, modules):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.requires_salt_modules({})
        def test_one():
            assert True
        """.format(
            ", ".join(repr(module) for module in modules)
        )
    )
    res = pytester.runpytest()
    # res.assert_outcomes(passed=1)
    assert res.parseoutcomes()["passed"] == 1
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")


@pytest.mark.parametrize(
    "modules",
    [
        ("cmdmod",),
        ("cmd", "tests"),
    ],
)
def test_missing_required_salt_module(pytester, modules):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.requires_salt_modules({})
        def test_one():
            assert True
        """.format(
            ", ".join(repr(module) for module in modules)
        )
    )
    res = pytester.runpytest()
    # res.assert_outcomes(skipped=1)
    assert res.parseoutcomes()["skipped"] == 1
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")


def test_has_required_custom_salt_module(pytester):
    pytester.makepyfile(
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
            defaults = {
                "root_dir": str(root_dir),
            }
            overrides = {
                "file_client": "local",
                "features": {"enable_slsvars_fixes": True},
                "file_roots": {
                    "base": [str(rootfs)]
                }
            }
            factory = salt_factories.salt_minion_daemon(
                minion_id, defaults=defaults, overrides=overrides,
            )
            loader_instance = saltfactories.utils.functional.Loaders(factory.config.copy())
            assert loader_instance.modules.bogus.echo("foo") == "foo"
            return loader_instance

        @pytest.mark.requires_salt_modules(custom_module_name)
        def test_custom_module():
            assert True
        """
    )
    res = pytester.runpytest()
    # res.assert_outcomes(passed=1)
    assert res.parseoutcomes()["passed"] == 1
    res.stdout.no_fnmatch_line("*PytestUnknownMarkWarning*")


def test_marker_does_not_accept_keyword_argument(pytester):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.requires_salt_modules("cmd", foo=True)
        def test_one():
            assert True
        """
    )
    res = pytester.runpytest()
    # res.assert_outcomes(errors=1)
    assert res.parseoutcomes()["errors"] == 1
    res.stdout.fnmatch_lines(
        ["*UsageError: The 'required_salt_modules' marker does not accept keyword arguments*"]
    )


def test_marker_only_accepts_string_arguments(pytester):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.requires_salt_modules(("cmd", "test"))
        def test_one():
            assert True
        """
    )
    res = pytester.runpytest()
    # res.assert_outcomes(errors=1)
    assert res.parseoutcomes()["errors"] == 1
    res.stdout.fnmatch_lines(
        ["*UsageError: The 'required_salt_modules' marker only accepts strings as arguments*"]
    )


def test_marker_errors_with_no_arguments(pytester):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.requires_salt_modules
        def test_one():
            assert True
        """
    )
    res = pytester.runpytest()
    # res.assert_outcomes(errors=1)
    assert res.parseoutcomes()["errors"] == 1
    res.stdout.fnmatch_lines(
        [
            "*UsageError: The 'required_salt_modules' marker needs at least one module name to be passed*"
        ]
    )
