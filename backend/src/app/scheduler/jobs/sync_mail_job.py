"""
Job APScheduler synchronizujący skrzynkę (IMAP) - osobny, wolniejszy
cykl niż zamówienia (co 5 minut, nie co 60s), bo częsty polling bywa
throttlowany przez dostawców poczty (zwłaszcza Gmail/iCloud).

Tak jak job zamówień pilnuje serii awarii (`SyncFailureTracker`): poczta
to JEDYNE źródło sprzedaży z Allegro Lokalnie i OLX, więc jej awaria nie
może kończyć się wyłącznie wpisem w logu. Wcześniej job połykał błąd
logowania IMAP po cichu - zepsute hasło aplikacji oznaczało zamówienia,
o których nikt się nie dowiadywał.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.interfaces.notifier import Notifier
from app.infrastructure.mail.imap_watcher import ImapConnectionError, ImapLoginRejectedError
from app.scheduler.sync_failure_tracker import SyncFailureTracker
from app.services.mailbox_service import MailboxService

#: Klucz serii awarii w `SyncFailureTracker` - tracker jest wspólny
#: z synchronizacją zamówień, więc kanały muszą mieć różne nazwy.
MAIL_CHANNEL = "poczta"


async def run_mail_sync_job(
    session_scope_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    build_mailbox_service: Callable[[AsyncSession], MailboxService],
    failure_tracker: SyncFailureTracker | None = None,
    notifier: Notifier | None = None,
    retry_in_minutes: int = 5,
) -> None:
    """
    Wykonuje jeden cykl synchronizacji skrzynki w bezpiecznej sesji bazy.

    Zdarzenia (Allegro Lokalnie, OLX, dyskusje) są publikowane dopiero po
    zamknięciu sesji - dokładnie jak w `run_sync_orders_job`, bo
    subskrybenci piszą do bazy we własnych sesjach i muszą widzieć
    zatwierdzone dane.

    Args:
        session_scope_factory: Fabryka context managera sesji.
        build_mailbox_service: Funkcja budująca MailboxService dla sesji.
        failure_tracker: Licznik serii awarii. Gdy None, alert o
            niedziałającej poczcie nie jest wysyłany.
        notifier: Kanał powiadomień dla tego alertu.
        retry_in_minutes: Za ile minut job ruszy ponownie - trafia do treści.
    """
    try:
        async with session_scope_factory() as session:
            mailbox_service = build_mailbox_service(session)
            saved = await mailbox_service.sync_now()
    except ImapConnectionError as exc:
        logger.warning("Synchronizacja skrzynki IMAP nie powiodła się: {}", exc)
        await _maybe_alert(
            failure_tracker,
            notifier,
            login_rejected=isinstance(exc, ImapLoginRejectedError),
            retry_in_minutes=retry_in_minutes,
        )
        return
    except Exception:
        logger.exception("Nieoczekiwany błąd podczas synchronizacji skrzynki")
        return

    # Skrzynka odpowiedziała (albo IMAP jest świadomie wyłączony) - seria
    # awarii się kończy, kolejna zacznie liczenie od zera.
    if failure_tracker is not None:
        failure_tracker.record_success(MAIL_CHANNEL)

    try:
        await mailbox_service.publish_mail_events(saved)
    except Exception:
        logger.exception("Nie udało się opublikować zdarzeń z nowych maili")
    if saved:
        logger.info("Skrzynka: wykryto {} nowych maili", len(saved))


async def _maybe_alert(
    failure_tracker: SyncFailureTracker | None,
    notifier: Notifier | None,
    *,
    login_rejected: bool,
    retry_in_minutes: int,
) -> None:
    """
    Wysyła alert o niedziałającej poczcie przy DRUGIEJ awarii z rzędu -
    i tylko raz na serię, nie co 5 minut.

    Awaria samego powiadamiania nie może przewrócić joba - to poboczny
    efekt, nie jego zadanie.
    """
    if failure_tracker is None or notifier is None:
        return
    if not failure_tracker.record_failure(MAIL_CHANNEL):
        return
    try:
        await notifier.notify_mailbox_unavailable(
            login_rejected=login_rejected, retry_in_minutes=retry_in_minutes
        )
    except Exception:
        logger.exception("Nie udało się wysłać powiadomienia o niedziałającej poczcie")
