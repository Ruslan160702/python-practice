"""Persistent user data. Every personal record is scoped to a Telegram user."""
import json
from datetime import datetime, timezone

from peewee import (AutoField, CharField, DateTimeField, ForeignKeyField,
                    Model, TextField, IntegrityError)

from .db import database


class BaseModel(Model):
    class Meta:
        database = database


class User(BaseModel):
    telegram_id = CharField(unique=True)
    username = CharField(null=True)
    first_name = CharField(null=True)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    @classmethod
    def ensure(cls, telegram_id: int, username: str | None = None,
               first_name: str | None = None):
        user, created = cls.get_or_create(
            telegram_id=str(telegram_id),
            defaults={"username": username, "first_name": first_name},
        )
        if not created and (username != user.username or first_name != user.first_name):
            cls.update(username=username, first_name=first_name).where(cls.id == user.id).execute()
            user = cls.get_by_id(user.id)
        return user


class SearchHistory(BaseModel):
    user = ForeignKeyField(User, backref="searches", on_delete="CASCADE")
    query = CharField()
    searched_at = DateTimeField(default=lambda: datetime.now(timezone.utc))


class MovieListEntry(BaseModel):
    user = ForeignKeyField(User, backref="%(class)s_entries", on_delete="CASCADE")
    movie_id = CharField()
    title = CharField(default="Без названия")
    movie_json = TextField(default="{}")
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    class Meta:
        indexes = ((('user', 'movie_id'), True),)

    @property
    def movie(self) -> dict:
        try:
            value = json.loads(self.movie_json)
            return value if isinstance(value, dict) else {}
        except (TypeError, json.JSONDecodeError):
            return {}


class Favorite(MovieListEntry):
    pass


class WatchedMovie(MovieListEntry):
    pass


class Watchlist(MovieListEntry):
    pass


LIST_MODELS = {"favorite": Favorite, "watched": WatchedMovie, "watchlist": Watchlist}


def toggle_movie(model: type[MovieListEntry], user: User, movie: dict) -> bool:
    """Toggle a movie in a user's list; return True when it is now present."""
    movie_id = str(movie.get("id", "")).strip()
    if not movie_id:
        raise ValueError("В ответе API отсутствует id фильма")
    existing = model.get_or_none((model.user == user) & (model.movie_id == movie_id))
    if existing:
        existing.delete_instance()
        return False
    title = movie.get("name") or movie.get("alternativeName") or movie.get("enName") or "Без названия"
    try:
        model.create(user=user, movie_id=movie_id, title=title,
                     movie_json=json.dumps(movie, ensure_ascii=False))
    except IntegrityError:
        return True
    return True


def add_search(user: User, query: str) -> SearchHistory:
    return SearchHistory.create(user=user, query=query.strip()[:200])
