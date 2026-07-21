"""
Job APScheduler czyszczący czat Telegram i publikujący aktualne zamówienia (02:00).

Dwie fazy czyszczenia działają w osobnych, kolejno zatwierdzanych sesjach -
faza usuwania zapisuje do tabeli telegram_messages, a faza publikacji wyzwala
zapis middleware sesji bota. Rozdzielenie transakcji zapobiega zakleszczeniu
zapisu w SQLite (szczegóły w TelegramCleanupService).
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.telegram_cleanup_service import TelegramCleanupService


async def run_telegram_cleanup_job(
    session_scope_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    build_cleanup_service: Callable[[AsyncSession], TelegramCleanupService],
) -> None:
    """
    Wykonuje nocne czyszczenie czatu w dwóch odrębnych transakcjach.

    Args:
        session_scope_factory: Fabryka context managera sesji bazy danych.
        build_cleanup_service: Funkcja budująca TelegramCleanupService.
    """
    try:
        async with session_scope_factory() as session:
            deleted = await build_cleanup_service(session).purge_previous_messages()

        async with session_scope_factory() as session:
            reposted = await build_cleanup_service(session).repost_active_orders()

        logger.info(
            "Nocne czyszczenie czatu zakończone: usunięto {}, opublikowano {}",
            deleted,
            reposted,
        )
    except Exception:
        logger.exception("Zaplanowane czyszczenie czatu Telegram nie powiodło się")
