import json

import pytest

from database.db import database, initialize_database
from database.models import Favorite, SearchHistory, User, WatchedMovie, Watchlist, add_search, toggle_movie
from services.recommendation import recommendation_filters


@pytest.fixture(autouse=True)
def temporary_database(tmp_path):
    if not database.is_closed():
        database.close()
    initialize_database(str(tmp_path / "test.sqlite3"))
    yield
    if not database.is_closed():
        database.close()


def test_user_creation_and_scoped_search_history():
    first = User.ensure(1001, "first", "One")
    same = User.ensure(1001, "first", "One")
    second = User.ensure(1002, "second", "Two")
    assert first.id == same.id
    add_search(first, "Матрица")
    assert SearchHistory.select().where(SearchHistory.user == first).count() == 1
    assert SearchHistory.select().where(SearchHistory.user == second).count() == 0


@pytest.mark.parametrize("model", [Favorite, WatchedMovie, Watchlist])
def test_each_personal_list_toggles_and_deduplicates(model):
    user = User.ensure(2001)
    movie = {"id": 42, "name": "Тест", "genres": [{"name": "драма"}]}
    assert toggle_movie(model, user, movie) is True
    assert toggle_movie(model, user, movie) is False
    assert model.select().where(model.user == user).count() == 0


def test_personal_lists_are_separated_by_user():
    first, second = User.ensure(3001), User.ensure(3002)
    toggle_movie(Favorite, first, {"id": 5, "name": "Фильм"})
    assert Favorite.select().where(Favorite.user == first).count() == 1
    assert Favorite.select().where(Favorite.user == second).count() == 0
    assert json.loads(Favorite.get().movie_json)["name"] == "Фильм"


def test_recommendations_use_saved_genre_and_rating():
    user = User.ensure(4001)
    toggle_movie(Favorite, user, {"id": 8, "name": "Фильм", "genres": [{"name": "драма"}],
                                  "rating": {"kp": 8.5}})
    filters, description = recommendation_filters(user)
    assert filters["genres.name"] == "драма"
    assert filters["rating.kp"] == "7.5-10"
    assert "ваших списков" in description
