"""
Endpointy HTTP /api/v1/stock/* - odpowiednik komend /stock dla
aplikacji mobilnej (Inventory Management System).

Uwaga o kolejności tras: `/stock/report` i `/stock/shopping-list` muszą
być zadeklarowane PRZED `/stock/{sku}`, z tego samego powodu co w
`orders.py`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_container, get_session
from app.api.schemas import (
    StockAdjustIn,
    StockCreateIn,
    StockItemOut,
    StockLinkIn,
    StockMovementOut,
    StockReportOut,
    stock_item_out,
    stock_movement_out,
    stock_report_out,
)
from app.container import Container

router = APIRouter()


@router.get("/stock/report", response_model=StockReportOut)
async def get_stock_report(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StockReportOut:
    """Raport magazynowy: wartość, niskie stany, prognoza, brak sprzedaży."""
    inventory_service = container.inventory_service(session)
    report = await inventory_service.get_report()
    return stock_report_out(report)


@router.get("/stock/shopping-list", response_model=list[StockItemOut])
async def get_shopping_list(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[StockItemOut]:
    """Produkty poniżej minimalnego stanu - lista zakupów."""
    inventory_service = container.inventory_service(session)
    items = await inventory_service.get_shopping_list()
    return [stock_item_out(i) for i in items]


@router.post(
    "/stock/links", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
async def link_offer(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: StockLinkIn,
) -> None:
    """Mapuje ofertę marketplace na produkt magazynowy (obsługa zestawów)."""
    inventory_service = container.inventory_service(session)
    await inventory_service.link_offer(
        payload.marketplace, payload.external_product_id, payload.sku, payload.quantity
    )


@router.delete(
    "/stock/links/{marketplace}/{external_product_id}",
    response_model=dict,
)
async def unlink_offer(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    marketplace: str,
    external_product_id: str,
) -> dict:
    """Usuwa mapowanie oferty marketplace. Zwraca liczbę usuniętych składników."""
    inventory_service = container.inventory_service(session)
    removed = await inventory_service.unlink_offer(marketplace, external_product_id)
    return {"removed": removed}


@router.get("/stock", response_model=list[StockItemOut])
async def list_stock(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[StockItemOut]:
    """Zwraca wszystkie produkty magazynowe."""
    inventory_service = container.inventory_service(session)
    items = await inventory_service.get_stock_overview()
    return [stock_item_out(i) for i in items]


@router.post("/stock", response_model=StockItemOut, status_code=status.HTTP_201_CREATED)
async def create_stock_item(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: StockCreateIn,
) -> StockItemOut:
    """Tworzy nowy produkt magazynowy ze stanem początkowym 0."""
    inventory_service = container.inventory_service(session)
    item = await inventory_service.create_item(
        payload.sku, payload.name, payload.min_stock
    )
    return stock_item_out(item)


@router.get("/stock/{sku}", response_model=StockItemOut)
async def get_stock_item(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    sku: str,
) -> StockItemOut:
    """Zwraca szczegóły jednego produktu magazynowego."""
    inventory_service = container.inventory_service(session)
    item = await inventory_service.get_item(sku)
    return stock_item_out(item)


@router.post("/stock/{sku}/adjust", response_model=StockItemOut)
async def adjust_stock(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    sku: str,
    payload: StockAdjustIn,
) -> StockItemOut:
    """
    Koryguje stan magazynowy: `op` = `set` | `add` | `remove` | `min`.

    Odpowiednik komend `/stock set|add|remove|min SKU ilość` w bocie.
    """
    inventory_service = container.inventory_service(session)
    reason = payload.reason

    if payload.op == "set":
        item = await (
            inventory_service.set_stock(sku, payload.quantity, reason)
            if reason
            else inventory_service.set_stock(sku, payload.quantity)
        )
    elif payload.op == "add":
        item = await (
            inventory_service.add_stock(sku, payload.quantity, reason)
            if reason
            else inventory_service.add_stock(sku, payload.quantity)
        )
    elif payload.op == "remove":
        item = await (
            inventory_service.remove_stock(sku, payload.quantity, reason)
            if reason
            else inventory_service.remove_stock(sku, payload.quantity)
        )
    else:
        item = await inventory_service.set_min_stock(sku, payload.quantity)

    return stock_item_out(item)


@router.get("/stock/{sku}/history", response_model=list[StockMovementOut])
async def get_stock_history(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    sku: str,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[StockMovementOut]:
    """Historia zmian magazynowych dla jednego SKU."""
    inventory_service = container.inventory_service(session)
    movements = await inventory_service.get_history(sku, limit)
    return [stock_movement_out(m) for m in movements]
