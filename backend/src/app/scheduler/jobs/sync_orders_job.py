"""
Job APScheduler wywoływany cyklicznie co N sekund.

Ta funkcja jest celowo bardzo cienka - cała logika żyje w
SyncOrdersService. Jedyny wyjątek to decyzja o powiadomieniu
o niedostępnym kanale, bo wymaga pamięci między cyklami
(patrz `SyncFailureTracker`).
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions.domain_exceptions import MarketplaceUnavailableError
from app.domain.interfaces.notifier import Notifier
from app.scheduler.sync_failure_tracker import SyncFailureTracker
from app.services.health_service import SyncStatus
from app.services.sync_orders_service import SyncOrdersService


async def run_sync_orders_job(
    session_scope_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    build_sync_service: Callable[[AsyncSession], SyncOrdersService],
    sync_status: SyncStatus,
    failure_tracker: SyncFailureTracker | None = None,
    notifier: Notifier | None = None,
    channel: str = "allegro",
    retry_in_minutes: int = 1,
) -> None:
    """
    Wykonuje jeden cykl synchronizacji zamówień w bezpiecznej sesji bazy.

    Zdarzenia (OrderCreated, SyncFinished) są publikowane dopiero po
    zamknięciu sesji - subskrybenci piszą do bazy we własnych sesjach
    i muszą widzieć zatwierdzone dane.

    Args:
        session_scope_factory: Fabryka context managera sesji.
        build_sync_service: Funkcja budująca SyncOrdersService dla danej sesji.
        sync_status: Współdzielony znacznik ostatniej udanej synchronizacji.
        failure_tracker: Licznik serii awarii. Gdy None, powiadomienie
            o niedostępnym kanale nie jest wysyłane (tak działają testy,
            które nie sprawdzają tej ścieżki).
        notifier: Kanał powiadomień - używany wyłącznie do alertu
            o niedostępności marketplace.
        channel: Nazwa kanału do treści powiadomienia.
        retry_in_minutes: Za ile minut będzie kolejna próba - trafia
            wprost do treści, bo błąd ma mówić, co dalej (sekcja 7.3).
    """
    try:
        async with session_scope_factory() as session:
            sync_service = build_sync_service(session)
            result = await sync_service.sync_new_orders()

        await sync_service.publish_sync_events(result)
        sync_status.mark_sync_completed()
        if failure_tracker is not None:
            failure_tracker.record_success(channel)
        logger.info(
            "Synchronizacja zakończona: {} nowych, {} sprawdzonych, "
            "{} anulowanych, {} nowych zwrotów",
            result.new_orders_count,
            result.checked_orders_count,
            len(result.cancelled_orders),
            len(result.new_returns),
        )
    except MarketplaceUnavailableError:
        logger.warning(
            "Allegro API niedostępne podczas zaplanowanej synchronizacji - "
            "ponowna próba przy następnym cyklu"
        )
        await _maybe_alert(failure_tracker, notifier, channel, retry_in_minutes)
    except Exception:
        logger.exception("Nieoczekiwany błąd podczas zaplanowanej synchronizacji")
        await _maybe_alert(failure_tracker, notifier, channel, retry_in_minutes)


async def _maybe_alert(
    failure_tracker: SyncFailureTracker | None,
    notifier: Notifier | None,
    channel: str,
    retry_in_minutes: int,
) -> None:
    """
    Wysyła powiadomienie o niedostępnym kanale, gdy seria awarii
    przekroczyła próg.

    Awaria samego powiadamiania nie może przewrócić joba synchronizacji -
    to poboczny efekt, nie jego zadanie.
    """
    if failure_tracker is None or notifier is None:
        return
    if not failure_tracker.record_failure(channel):
        return

    try:
        await notifier.notify_sync_failed(channel=channel, retry_in_minutes=retry_in_minutes)
    except Exception:
        logger.exception("Nie udało się wysłać powiadomienia o niedostępności {}", channel)
