"""
Job APScheduler synchronizujący skrzynkę (IMAP) - osobny, wolniejszy
cykl niż zamówienia (co 5 minut, nie co 60s), bo częsty polling bywa
throttlowany przez dostawców poczty (zwłaszcza Gmail/iCloud).
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.mailbox_service import MailboxService


async def run_mail_sync_job(
    session_scope_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    build_mailbox_service: Callable[[AsyncSession], MailboxService],
) -> None:
    """Wykonuje jeden cykl synchronizacji skrzynki w bezpiecznej sesji bazy."""
    try:
        async with session_scope_factory() as session:
            mailbox_service = build_mailbox_service(session)
            new_count = await mailbox_service.sync_new_mail()
        if new_count:
            logger.info("Skrzynka: wykryto {} nowych maili", new_count)
    except Exception:
        logger.exception("Nieoczekiwany błąd podczas synchronizacji skrzynki")
