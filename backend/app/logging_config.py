"""Logging setup for the TurfSlot API."""

import logging
import logging.config

from app.config import settings

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_logging(level: str | None = None) -> None:
    """Configure root logging with a single stream handler.

    Args:
        level: Log level name; defaults to ``settings.LOG_LEVEL``.
    """
    log_level = (level or settings.LOG_LEVEL).upper()
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"default": {"format": LOG_FORMAT}},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                }
            },
            "root": {"level": log_level, "handlers": ["console"]},
            "loggers": {
                "uvicorn.access": {"level": "INFO"},
                "sqlalchemy.engine": {"level": "WARNING"},
                "apscheduler": {"level": "WARNING"},
            },
        }
    )
