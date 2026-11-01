"""Application configuration loaded from environment variables."""
from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    poiskkino_api_key: str = os.getenv("POISKKINO_API_KEY", "")
    database_path: str = os.getenv("DATABASE_PATH", "movie_finder.sqlite3")
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()


settings = Settings()
