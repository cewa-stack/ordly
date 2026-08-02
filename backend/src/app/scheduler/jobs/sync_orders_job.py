"""
Job APScheduler wywoływany cyklicznie co N sekund.

Ta funkcja jest celowo bardzo cienka - cała logika żyje w
SyncOrdersService.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions.domain_exceptions import MarketplaceUnavailableError
from app.services.health_service import SyncStatus
from app.services.sync_orders_service import SyncOrdersService


async def run_sync_orders_job(
    session_scope_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    build_sync_service: Callable[[AsyncSession], SyncOrdersService],
    sync_status: SyncStatus,
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
    """
    try:
        async with session_scope_factory() as session:
            sync_service = build_sync_service(session)
            result = await sync_service.sync_new_orders()

        await sync_service.publish_sync_events(result)
        sync_status.mark_sync_completed()
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
    except Exception:
        logger.exception("Nieoczekiwany błąd podczas zaplanowanej synchronizacji")
