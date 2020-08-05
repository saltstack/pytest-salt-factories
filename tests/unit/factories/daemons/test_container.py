from unittest import mock

import pytest

from saltfactories.factories.daemons.container import ContainerFactory


def test_missing_docker_library():
    with mock.patch(
        "saltfactories.factories.daemons.container.HAS_DOCKER",
        new_callable=mock.PropertyMock(return_value=False),
    ):
        with pytest.raises(RuntimeError) as exc:
            ContainerFactory(name="foo", image="bar")

        assert str(exc.value) == "The docker python library was not found installed"


def test_missing_requests_library():
    with mock.patch(
        "saltfactories.factories.daemons.container.HAS_REQUESTS",
        new_callable=mock.PropertyMock(return_value=False),
    ):
        with pytest.raises(RuntimeError) as exc:
            ContainerFactory(name="foo", image="bar")

        assert str(exc.value) == "The requests python library was not found installed"
