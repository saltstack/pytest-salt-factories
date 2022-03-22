from unittest import mock

import pytest

from saltfactories.daemons.container import Container


def test_missing_docker_library():
    with mock.patch(
        "saltfactories.daemons.container.HAS_DOCKER",
        new_callable=mock.PropertyMock(return_value=False),
    ):
        with pytest.raises(pytest.fail.Exception) as exc:
            Container(name="foo", image="bar")

        assert str(exc.value) == "The docker python library was not found installed"


def test_missing_requests_library():
    with mock.patch(
        "saltfactories.daemons.container.HAS_DOCKER",
        new_callable=mock.PropertyMock(return_value=True),
    ), mock.patch(
        "saltfactories.daemons.container.HAS_REQUESTS",
        new_callable=mock.PropertyMock(return_value=False),
    ):
        with pytest.raises(pytest.fail.Exception) as exc:
            Container(name="foo", image="bar")

        assert str(exc.value) == "The requests python library was not found installed"
