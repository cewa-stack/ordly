"""Job APScheduler wykonujący cykliczny backup bazy danych (raz dziennie)."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from loguru import logger

from app.services.backup_service import BackupService


async def run_backup_job(
    session_scope_factory: Callable[[], AbstractAsyncContextManager],
    build_backup_service: Callable[..., BackupService],
) -> None:
    """
    Wykonuje jeden cykl tworzenia kopii zapasowej w bezpiecznej sesji.

    Args:
        session_scope_factory: Fabryka context managera sesji bazy danych.
        build_backup_service: Funkcja budująca BackupService dla danej sesji.
    """
    try:
        async with session_scope_factory() as session:
            backup_service = build_backup_service(session)
            await backup_service.create_backup()
    except Exception:
        logger.exception("Zaplanowany backup bazy danych nie powiódł się")
