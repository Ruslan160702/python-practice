from unittest.mock import Mock

import pytest
import requests

from services.movie_api import MovieApi, MovieApiError


def response(payload, status=200):
    item = Mock()
    item.status_code = status
    item.json.return_value = payload
    item.raise_for_status.return_value = None
    return item


def test_search_uses_documented_route_and_auth_header():
    session = Mock()
    session.get.return_value = response({"docs": [{"id": 1}]})
    client = MovieApi("secret", session=session)
    assert client.search_title("Матрица", 2, 8)["docs"][0]["id"] == 1
    args, kwargs = session.get.call_args
    assert args[0].endswith("/v1.5/movie/search")
    assert kwargs["params"] == {"query": "Матрица", "page": 2, "limit": 8}
    assert kwargs["headers"] == {"X-API-KEY": "secret"}


def test_missing_key_fails_without_request():
    session = Mock()
    with pytest.raises(MovieApiError, match="Не настроен ключ"):
        MovieApi("", session=session).random_movie()
    session.get.assert_not_called()


@pytest.mark.parametrize("status,fragment", [(401, "недействителен"), (403, "лимит"), (404, "не найден")])
def test_http_statuses_are_presented_as_safe_errors(status, fragment):
    session = Mock()
    session.get.return_value = response({}, status)
    with pytest.raises(MovieApiError, match=fragment):
        MovieApi("secret", session=session).get_movie(1)


def test_timeout_is_handled():
    session = Mock()
    session.get.side_effect = requests.Timeout
    with pytest.raises(MovieApiError, match="вовремя"):
        MovieApi("secret", session=session).random_movie()
