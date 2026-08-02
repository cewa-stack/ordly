"""
Centralna konfiguracja logowania (Loguru) dla całej aplikacji.

Wywoływana dokładnie raz, na samym początku uruchamiania aplikacji
(app/main.py) - powtórne wywołanie spowodowałoby zdublowanie
handlerów i logi pojawiałyby się wielokrotnie w plikach.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from loguru import logger

from app.core.config import LoggingSettings


class InterceptHandler(logging.Handler):
    """
    Przechwytuje logi ze standardowego modułu `logging` i przekierowuje
    je przez Loguru.

    Biblioteki takie jak aiogram, SQLAlchemy i APScheduler logują przez
    standardowy `logging`, nie przez Loguru - bez tego mostka ich logi
    ominęłyby nasze pliki i format, utrudniając diagnostykę.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """Tłumaczy pojedynczy rekord logu ze standardowego formatu na Loguru."""
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def configure_logging(settings: LoggingSettings, app_debug: bool) -> None:
    """
    Konfiguruje Loguru: format, poziomy, rotację, retencję i przechwytywanie
    logów z bibliotek zewnętrznych.

    Args:
        settings: Konfiguracja logowania (katalog, rotacja, retencja).
        app_debug: Czy aplikacja działa w trybie debug.

    Musi być wywołana dokładnie raz, na samym początku main.py, przed
    jakimkolwiek innym importem, który mógłby coś zalogować.
    """
    logger.remove()

    log_directory = Path(settings.log_directory)
    log_directory.mkdir(parents=True, exist_ok=True)

    console_level = "DEBUG" if app_debug else "INFO"
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    logger.add(
        sys.stdout,
        level=console_level,
        format=log_format,
        colorize=True,
        backtrace=True,
        diagnose=False,
    )

    logger.add(
        log_directory / "app.log",
        level="INFO",
        format=log_format,
        rotation=settings.rotation,
        retention=f"{settings.retention_days} days",
        compression="zip",
        backtrace=True,
        diagnose=False,
        enqueue=True,
    )

    logger.add(
        log_directory / "errors.log",
        level="ERROR",
        format=log_format,
        rotation=settings.rotation,
        retention=f"{settings.retention_days} days",
        compression="zip",
        backtrace=True,
        diagnose=False,
        enqueue=True,
    )

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for noisy_logger_name in ("aiogram", "apscheduler", "sqlalchemy.engine", "httpx"):
        noisy_logger = logging.getLogger(noisy_logger_name)
        noisy_logger.handlers = [InterceptHandler()]
        noisy_logger.propagate = False

    logger.info(
        "Logowanie skonfigurowane: konsola={}, katalog={}, rotacja={}, retencja={}dni",
        console_level,
        log_directory,
        settings.rotation,
        settings.retention_days,
    )
