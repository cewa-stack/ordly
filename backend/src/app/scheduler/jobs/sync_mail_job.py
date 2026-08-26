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
    """
    Wykonuje jeden cykl synchronizacji skrzynki w bezpiecznej sesji bazy.

    Zdarzenia (dziś: powiadomienia z Allegro Lokalnie) są publikowane
    dopiero po zamknięciu sesji - dokładnie jak w `run_sync_orders_job`,
    bo subskrybenci piszą do bazy we własnych sesjach i muszą widzieć
    zatwierdzone dane.
    """
    try:
        async with session_scope_factory() as session:
            mailbox_service = build_mailbox_service(session)
            saved = await mailbox_service.sync_new_mail_messages()

        await mailbox_service.publish_mail_events(saved)
        if saved:
            logger.info("Skrzynka: wykryto {} nowych maili", len(saved))
    except Exception:
        logger.exception("Nieoczekiwany błąd podczas synchronizacji skrzynki")
