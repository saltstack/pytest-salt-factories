import shutil
import sys

import pytest
from pytestshellutils.exceptions import FactoryNotStarted

from saltfactories.bases import SaltDaemon


@pytest.fixture
def config_dir(pytester):
    _conf_dir = pytester.mkdir("conf")
    try:
        yield _conf_dir
    finally:
        shutil.rmtree(str(_conf_dir), ignore_errors=True)


@pytest.fixture
def master_id():
    return "test-master-id"


@pytest.fixture
def config_file(config_dir, master_id):
    config_file = str(config_dir / "config")
    with open(config_file, "w", encoding="utf-8") as wfh:
        wfh.write(f"id: {master_id}\n")
    return config_file


def test_extra_cli_arguments_after_first_failure(
    config_dir, config_file, tempfiles, master_id, tmp_path
):
    """
    This test asserts that after the first start failure, the extra_cli_arguments_after_first_start_failure
    arguments are added.
    """
    output_file = tmp_path.joinpath("output.txt").resolve()
    config = {"conf_file": config_file, "id": master_id}
    script = tempfiles.makepyfile(
        rf"""
        # coding=utf-8

        import sys
        import multiprocessing

        def main():
            with open(r"{output_file}", "a", encoding="utf-8") as wfh:
                wfh.write(" ".join(sys.argv))
                wfh.write("\n")
            sys.exit(1)

        # Support for windows test runs
        if __name__ == '__main__':
            multiprocessing.freeze_support()
            main()
        """,
    )
    daemon = SaltDaemon(
        script_name=script,
        config=config,
        start_timeout=0.25,
        max_start_attempts=2,
        check_ports=[12345],
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
        python_executable=sys.executable,
    )
    with pytest.raises(FactoryNotStarted) as exc:
        with daemon.started():
            pass

    str_exc = str(exc.value)
    output_file_contents = output_file.read_text().splitlines()
    expected = [
        f"{script} --config-dir={config_dir} --log-level=critical",
        f"{script} --config-dir={config_dir} --log-level=debug",
    ]
    assert output_file_contents == expected
    assert "Returncode: 1" in str_exc
