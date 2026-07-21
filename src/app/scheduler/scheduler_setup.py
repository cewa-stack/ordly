"""Konfiguracja i uruchomienie APScheduler dla zadań cyklicznych."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger


def create_scheduler() -> AsyncIOScheduler:
    """Tworzy instancję schedulera APScheduler (jeszcze nieuruchomioną)."""
    return AsyncIOScheduler(timezone="Europe/Warsaw")


def register_sync_orders_job(
    scheduler: AsyncIOScheduler,
    job_coroutine: Callable[[], Awaitable[None]],
    interval_seconds: int,
) -> None:
    """
    Rejestruje job synchronizacji zamówień z podanym interwałem.

    Args:
        scheduler: Instancja schedulera zwrócona przez create_scheduler().
        job_coroutine: Bezargumentowa korutyna do wywołania cyklicznie.
        interval_seconds: Odstęp w sekundach między wywołaniami (domyślnie 60).
    """
    scheduler.add_job(
        job_coroutine,
        trigger="interval",
        seconds=interval_seconds,
        id="sync_orders_job",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=30,
    )
    logger.info("Zarejestrowano job synchronizacji zamówień co {}s", interval_seconds)


def register_backup_job(
    scheduler: AsyncIOScheduler,
    job_coroutine: Callable[[], Awaitable[None]],
) -> None:
    """
    Rejestruje codzienny job tworzenia kopii zapasowej bazy danych.

    Backup wykonywany jest raz dziennie o 3:00 w nocy czasu polskiego.

    Args:
        scheduler: Instancja schedulera zwrócona przez create_scheduler().
        job_coroutine: Bezargumentowa korutyna do wywołania codziennie.
    """
    scheduler.add_job(
        job_coroutine,
        trigger="cron",
        hour=3,
        minute=0,
        id="backup_job",
        max_instances=1,
        misfire_grace_time=3600,
    )
    logger.info("Zarejestrowano codzienny job backupu bazy danych (3:00)")


def register_shipping_reminder_job(
    scheduler: AsyncIOScheduler,
    job_coroutine: Callable[[], Awaitable[None]],
) -> None:
    """
    Rejestruje codzienny job przypomnienia o niewysłanych zamówieniach.

    Uruchamiany o 20:00 czasu polskiego (Europe/Warsaw).

    Args:
        scheduler: Instancja schedulera zwrócona przez create_scheduler().
        job_coroutine: Bezargumentowa korutyna do wywołania codziennie.
    """
    scheduler.add_job(
        job_coroutine,
        trigger="cron",
        hour=20,
        minute=0,
        id="shipping_reminder_job",
        max_instances=1,
        misfire_grace_time=1800,
    )
    logger.info("Zarejestrowano codzienny job przypomnienia o wysyłce (20:00)")


def register_telegram_cleanup_job(
    scheduler: AsyncIOScheduler,
    job_coroutine: Callable[[], Awaitable[None]],
) -> None:
    """
    Rejestruje codzienny job czyszczenia czatu Telegram.

    Uruchamiany o 02:00 czasu polskiego (Europe/Warsaw) - usuwa wszystkie
    wcześniejsze wiadomości bota i publikuje ponownie aktualne zamówienia.

    Args:
        scheduler: Instancja schedulera zwrócona przez create_scheduler().
        job_coroutine: Bezargumentowa korutyna do wywołania codziennie.
    """
    scheduler.add_job(
        job_coroutine,
        trigger="cron",
        hour=2,
        minute=0,
        id="telegram_cleanup_job",
        max_instances=1,
        misfire_grace_time=1800,
    )
    logger.info("Zarejestrowano codzienny job czyszczenia czatu Telegram (02:00)")
