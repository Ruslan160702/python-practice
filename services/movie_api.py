"""PoiskKino API client. Endpoint names and query syntax follow its v1.5 docs."""
from typing import Any

import requests


class MovieApiError(RuntimeError):
    """A safe, user-presentable API error without credentials or response dumps."""


class MovieApi:
    BASE_URL = "https://api.poiskkino.dev/v1.5"

    def __init__(self, api_key: str, timeout: float = 12.0,
                 session: requests.Session | None = None):
        self.api_key = api_key
        self.timeout = timeout
        self.session = session or requests.Session()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        if not self.api_key:
            raise MovieApiError("Не настроен ключ PoiskKino API. Добавьте POISKKINO_API_KEY в .env.")
        try:
            response = self.session.get(
                f"{self.BASE_URL}{path}", params=params,
                headers={"X-API-KEY": self.api_key}, timeout=self.timeout,
            )
            if response.status_code == 401:
                raise MovieApiError("Ключ PoiskKino API недействителен.")
            if response.status_code == 403:
                raise MovieApiError("Достигнут лимит PoiskKino API или тарифное ограничение пагинации.")
            if response.status_code == 404:
                raise MovieApiError("Фильм не найден.")
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise MovieApiError("API вернул неожиданный формат ответа.")
            return data
        except MovieApiError:
            raise
        except requests.Timeout as exc:
            raise MovieApiError("PoiskKino API не ответил вовремя. Попробуйте ещё раз.") from exc
        except requests.RequestException as exc:
            raise MovieApiError("Не удалось связаться с PoiskKino API.") from exc
        except ValueError as exc:
            raise MovieApiError("PoiskKino API вернул некорректный JSON.") from exc

    def search_title(self, query: str, page: int = 1, limit: int = 8) -> dict:
        return self._get("/movie/search", {"query": query, "page": page, "limit": limit})

    def search_filter(self, filters: dict[str, Any]) -> dict:
        return self._get("/movie", filters)

    def get_movie(self, movie_id: str | int) -> dict:
        value = str(movie_id)
        if not value.isdigit():
            raise MovieApiError("Некорректный идентификатор фильма.")
        return self._get(f"/movie/{value}")

    def random_movie(self, filters: dict[str, Any] | None = None) -> dict:
        return self._get("/movie/random", filters or {})

    def genres(self) -> dict:
        return self._get("/dictionary/genres")
