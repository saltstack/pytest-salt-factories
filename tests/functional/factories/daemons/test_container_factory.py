from unittest import mock

import pytest

from saltfactories.daemons.container import Container

docker = pytest.importorskip("docker")


@pytest.fixture(scope="module", autouse=True)
def _connectable_docker_client():
    try:
        client = docker.from_env()
        connectable = Container.client_connectable(client)
        if not connectable:
            pytest.skip(connectable)
    except docker.errors.DockerException as exc:
        pytest.skip("Failed to instantiate a docker client: {}".format(exc))


@pytest.mark.parametrize("skip_on_pull_failure", [True, False])
def test_skip_on_pull_failure(pytester, skip_on_pull_failure):
    pytester.makepyfile(
        """
        import pytest

        @pytest.fixture
        def container(salt_factories):
            factory = salt_factories.get_container(
                "skip_on_pull_failure-{0}",
                "non-existing/docker-container",
                pull_before_start=True,
                skip_on_pull_failure={0}
            )
            with factory.started() as factory:
                yield factory

        def test_container(container):
            assert container.is_running()
        """.format(
            skip_on_pull_failure
        )
    )
    res = pytester.runpytest()
    if skip_on_pull_failure:
        res.assert_outcomes(skipped=1)
    else:
        res.assert_outcomes(errors=1)


@pytest.mark.parametrize("skip_if_docker_client_not_connectable", [True, False])
def test_skip_if_docker_client_not_connectable(
    pytester, subtests, skip_if_docker_client_not_connectable
):
    pytester.makepyfile(
        """
        import pytest

        @pytest.fixture
        def container(salt_factories):
            factory = salt_factories.get_container(
                "skip_if_docker_client_not_connectable-{0}",
                "non-existing/docker-container",
                skip_if_docker_client_not_connectable={0}
            )
            with factory.started() as factory:
                yield factory

        def test_container(container):
            assert container.is_running()
        """.format(
            skip_if_docker_client_not_connectable
        )
    )
    with subtests.test("dockerpy not installed"):
        with mock.patch("saltfactories.daemons.container.HAS_DOCKER", False):
            res = pytester.runpytest_inprocess()
            if skip_if_docker_client_not_connectable:
                res.assert_outcomes(skipped=1)
            else:
                res.assert_outcomes(errors=1)
    with subtests.test("requests not installed"):
        with mock.patch("saltfactories.daemons.container.HAS_REQUESTS", False):
            res = pytester.runpytest_inprocess()
            if skip_if_docker_client_not_connectable:
                res.assert_outcomes(skipped=1)
            else:
                res.assert_outcomes(errors=1)
    with subtests.test("Container.client_connectable() is False"):
        with mock.patch(
            "saltfactories.daemons.container.Container.client_connectable",
            return_value="Not Connectable!",
        ):
            res = pytester.runpytest_inprocess()
            if skip_if_docker_client_not_connectable:
                res.assert_outcomes(skipped=1)
            else:
                res.assert_outcomes(errors=1)
