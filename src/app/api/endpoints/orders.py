"""
Endpointy HTTP /api/v1/orders/* - odpowiednik komend /orders, /order,
/search, /sync i /tracking dla aplikacji mobilnej.

Uwaga o kolejności tras: `/orders/search` i `/orders/sync` muszą być
zadeklarowane PRZED `/orders/{external_id}`, inaczej FastAPI dopasuje
"search"/"sync" jako wartość `external_id`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_container, get_session
from app.api.schemas import (
    OrderOut,
    ShipmentOut,
    SyncResultOut,
    order_out,
    shipment_out,
    sync_result_out,
)
from app.container import Container
from app.domain.exceptions.domain_exceptions import MarketplaceUnavailableError

router = APIRouter()


@router.get("/orders/search", response_model=list[OrderOut])
async def search_orders(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    q: Annotated[str, Query(min_length=1)],
) -> list[OrderOut]:
    """Wyszukuje zamówienia po numerze, kupującym lub nazwie produktu."""
    search_service = container.search_service(session)
    orders = await search_service.search_orders(q)
    return [order_out(o) for o in orders]


@router.post("/orders/sync", response_model=SyncResultOut)
async def trigger_sync(
    container: Annotated[Container, Depends(get_container)],
) -> SyncResultOut:
    """
    Wymusza natychmiastową synchronizację zamówień z marketplace.

    Otwiera własny zakres sesji (tak jak handler /sync w bocie) i
    publikuje zdarzenia dopiero PO zatwierdzeniu transakcji, żeby
    subskrybenci (np. powiadomienia) widzieli już zapisane dane.
    """
    try:
        async with container.session_scope() as session:
            sync_service = container.sync_orders_service(session)
            result = await sync_service.sync_new_orders()

        await sync_service.publish_sync_events(result)
        container.sync_status.mark_sync_completed()
    except MarketplaceUnavailableError:
        raise
    except Exception:
        logger.exception("Błąd podczas synchronizacji wywołanej przez TOOM API")
        raise

    return sync_result_out(result)


@router.get("/orders", response_model=list[OrderOut])
async def list_orders(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[OrderOut]:
    """Zwraca listę ostatnich zamówień (paginacja: `limit`/`offset`)."""
    orders_service = container.orders_service(session)
    orders = await orders_service.get_recent_orders(limit=limit, offset=offset)
    return [order_out(o) for o in orders]


@router.get("/orders/{external_id}", response_model=OrderOut)
async def get_order(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    external_id: str,
) -> OrderOut:
    """Zwraca szczegóły jednego zamówienia po numerze zewnętrznym."""
    orders_service = container.orders_service(session)
    order = await orders_service.get_order_by_external_id(external_id)
    return order_out(order)


@router.get("/orders/{external_id}/tracking", response_model=ShipmentOut)
async def get_order_tracking(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    external_id: str,
) -> ShipmentOut:
    """
    Zwraca aktualny status przesyłki, pobrany na żywo z marketplace
    (bez cache'owania do celów wyświetlania - tak jak komenda /tracking).
    """
    tracking_service = container.tracking_service(session)
    shipment = await tracking_service.get_current_tracking(external_id)
    return shipment_out(shipment)
