"""Structured logging for the application."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config.settings import LoggingConfig

#: Root logger name — all subsystem loggers are children of this.
ROOT_LOGGER_NAME = "market"


def configure_logging(config: LoggingConfig) -> None:
    """Configure the ``market`` root logger (console + optional file).

    Calling this multiple times re-configures and removes stale handlers, so
    tests and the CLI can reconfigure freely.
    """
    root = logging.getLogger(ROOT_LOGGER_NAME)
    root.handlers.clear()
    root.setLevel(config.level)

    formatter = logging.Formatter(config.format, datefmt="%Y-%m-%d %H:%M:%S")

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    if config.file_enabled and config.file_path:
        path = Path(config.file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            path, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    root.propagate = False
    root.setLevel(config.level)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger, e.g. ``market.data.validators``."""
    if name.startswith(ROOT_LOGGER_NAME + "."):
        return logging.getLogger(name)
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")


def log_event(
    logger: logging.Logger,
    event: str,
    message: str,
    level: int = logging.INFO,
    **fields: object,
) -> None:
    """Log an observability event in a consistent, greppable format.

    Output: ``EVENT=NAME MSG=... field=value ...``
    """
    pairs = " ".join(f"{k}={v}" for k, v in fields.items())
    logger.log(level, "EVENT=%s MSG=%s %s", event, message, pairs)