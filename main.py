"""Movie Finder Pro Telegram bot entry point."""
import logging

from telegram.ext import Application

from config import settings
from database.db import database, initialize_database
from handlers.bot import register_handlers
from services.movie_api import MovieApi
from utils.logging_config import configure_logging

logger = logging.getLogger(__name__)


async def on_startup(application: Application) -> None:
    initialize_database(settings.database_path)
    application.bot_data["movie_api"] = MovieApi(settings.poiskkino_api_key)
    logger.info("Database initialized; bot polling is starting")


async def on_shutdown(application: Application) -> None:
    if not database.is_closed():
        database.close()
    logger.info("Database connection closed")


def build_application() -> Application:
    if not settings.telegram_token:
        raise RuntimeError("Не задан TELEGRAM_BOT_TOKEN. Скопируйте .env.example в .env и добавьте токен.")
    application = (Application.builder().token(settings.telegram_token)
                   .post_init(on_startup).post_shutdown(on_shutdown).build())
    register_handlers(application)
    return application


def main() -> None:
    configure_logging(settings.log_level)
    try:
        build_application().run_polling(allowed_updates=["message", "callback_query"])
    except KeyboardInterrupt:
        logger.info("Stopped by operator")


if __name__ == "__main__":
    main()
