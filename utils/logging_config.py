import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(level: str = "INFO") -> None:
    Path("logs").mkdir(exist_ok=True)
    # httpx logs complete Telegram Bot API URLs at INFO, including the bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(),
                  RotatingFileHandler("logs/movie_finder.log", maxBytes=2_000_000,
                                      backupCount=3, encoding="utf-8")],
    )
