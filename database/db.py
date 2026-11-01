"""SQLite connection and schema initialization."""
from peewee import SqliteDatabase

database = SqliteDatabase(None, pragmas={"journal_mode": "wal", "foreign_keys": 1})


def initialize_database(path: str = "movie_finder.sqlite3") -> None:
    from .models import Favorite, SearchHistory, User, WatchedMovie, Watchlist

    database.init(path, pragmas={"journal_mode": "wal", "foreign_keys": 1})
    database.connect(reuse_if_open=True)
    database.create_tables([User, SearchHistory, Favorite, WatchedMovie, Watchlist], safe=True)
