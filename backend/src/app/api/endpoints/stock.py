"""
Endpointy HTTP /api/v1/stock/* - odpowiednik komend /stock dla
aplikacji mobilnej (Inventory Management System).

Uwaga o kolejności tras: `/stock/report` i `/stock/shopping-list` muszą
być zadeklarowane PRZED `/stock/{sku}`, z tego samego powodu co w
`orders.py`. Dotyczy to wyłącznie tras o TEJ SAMEJ liczbie segmentów -
`/stock/{sku}/sub-items` czy `/stock/{sku}/parent` nie kolidują
z niczym, bo ostatni segment jest w nich literałem.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_container, get_session
from app.api.schemas import (
    BackfillPlanOut,
    OfferRecipeIn,
    OfferRecipeOut,
    StockAdjustIn,
    StockCreateIn,
    StockDeleteOut,
    StockItemOut,
    StockLinkIn,
    StockMovementOut,
    StockReportOut,
    StockSetParentIn,
    UnmappedOfferOut,
    backfill_plan_out,
    offer_recipe_out,
    stock_delete_out,
    stock_item_out,
    stock_movement_out,
    stock_report_out,
    unmapped_offer_out,
)
from app.container import Container
from app.domain.entities.offer_component import OfferComponent
from app.services.offer_mapping_service import DEFAULT_LOOKBACK_DAYS

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


@router.post("/stock/links", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
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


@router.get("/stock/offers", response_model=list[OfferRecipeOut])
async def list_offer_recipes(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    days: Annotated[int, Query(ge=1, le=365)] = DEFAULT_LOOKBACK_DAYS,
) -> list[OfferRecipeOut]:
    """Receptury ofert - z czego magazynowo składa się każda oferta."""
    service = container.offer_mapping_service(session)
    recipes = await service.get_recipes(days)
    return [offer_recipe_out(r) for r in recipes]


@router.get("/stock/offers/unmapped", response_model=list[UnmappedOfferOut])
async def list_unmapped_offers(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    days: Annotated[int, Query(ge=1, le=365)] = DEFAULT_LOOKBACK_DAYS,
) -> list[UnmappedOfferOut]:
    """Oferty sprzedane bez receptury - ich sprzedaż nie rusza magazynu."""
    service = container.offer_mapping_service(session)
    offers = await service.get_unmapped_offers(days)
    return [unmapped_offer_out(o) for o in offers]


@router.put("/stock/offers/{marketplace}/{external_product_id}", response_model=OfferRecipeOut)
async def set_offer_recipe(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    marketplace: str,
    external_product_id: str,
    payload: OfferRecipeIn,
) -> OfferRecipeOut:
    """Zapisuje pełną recepturę oferty, zastępując poprzednią."""
    service = container.offer_mapping_service(session)
    recipe = await service.set_recipe(
        marketplace,
        external_product_id,
        [OfferComponent(sku=c.sku, quantity=c.quantity) for c in payload.components],
    )
    return offer_recipe_out(recipe)


@router.delete("/stock/offers/{marketplace}/{external_product_id}", response_model=dict)
async def delete_offer_recipe(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    marketplace: str,
    external_product_id: str,
) -> dict:
    """Usuwa recepturę oferty. Zwraca liczbę usuniętych składników."""
    service = container.offer_mapping_service(session)
    removed = await service.delete_recipe(marketplace, external_product_id)
    return {"removed": removed}


@router.get(
    "/stock/offers/{marketplace}/{external_product_id}/backfill",
    response_model=BackfillPlanOut,
)
async def preview_offer_backfill(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    marketplace: str,
    external_product_id: str,
    days: Annotated[int, Query(ge=1, le=365)] = DEFAULT_LOOKBACK_DAYS,
) -> BackfillPlanOut:
    """Podgląd korekty wstecznej: co zostanie odjęte i jaki będzie stan."""
    service = container.offer_mapping_service(session)
    plan = await service.plan_backfill(marketplace, external_product_id, days)
    return backfill_plan_out(plan)


@router.post(
    "/stock/offers/{marketplace}/{external_product_id}/backfill",
    response_model=BackfillPlanOut,
)
async def apply_offer_backfill(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    marketplace: str,
    external_product_id: str,
    days: Annotated[int, Query(ge=1, le=365)] = DEFAULT_LOOKBACK_DAYS,
) -> BackfillPlanOut:
    """
    Wykonuje korektę wsteczną - odejmuje sprzedaż sprzed powstania receptury.

    Rozliczenie idzie per zamówienie, więc powtórzenie żądania nie odejmie
    tych samych sztuk drugi raz.
    """
    service = container.offer_mapping_service(session)
    plan = await service.apply_backfill(marketplace, external_product_id, days)
    return backfill_plan_out(plan)


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
    item = await inventory_service.create_item(payload.sku, payload.name, payload.min_stock)
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


@router.delete("/stock/{sku}", response_model=StockDeleteOut)
async def delete_stock_item(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    sku: str,
) -> StockDeleteOut:
    """
    Usuwa produkt magazynowy razem z jego historią ruchów.

    Podprodukty zostają w magazynie - tracą tylko powiązanie z usuwanym
    produktem głównym. Odpowiedź mówi, co dokładnie usunięcie zmieniło
    poza samym zniknięciem wiersza z listy.
    """
    inventory_service = container.inventory_service(session)
    deletion = await inventory_service.delete_item(sku)
    return stock_delete_out(deletion)


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


@router.get("/stock/{sku}/sub-items", response_model=list[StockItemOut])
async def get_stock_sub_items(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    sku: str,
) -> list[StockItemOut]:
    """Podprodukty przypisane do produktu głównego (butelka -> nakrętka)."""
    inventory_service = container.inventory_service(session)
    items = await inventory_service.get_sub_items(sku)
    return [stock_item_out(i) for i in items]


@router.put("/stock/{sku}/parent", response_model=StockItemOut)
async def set_stock_parent(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    sku: str,
    payload: StockSetParentIn,
) -> StockItemOut:
    """
    Ustawia produkt główny dla danego SKU albo zdejmuje powiązanie
    (`parent_sku: null`).

    Złamanie reguły jednego poziomu zagnieżdżenia kończy się kodem 422
    z czytelnym komunikatem - `InventoryService` rzuca `ValueError`,
    a globalny handler z `api/errors.py` mapuje go tak jak każdą inną
    walidację w ORDLY.
    """
    inventory_service = container.inventory_service(session)
    item = await inventory_service.set_parent(sku, payload.parent_sku)
    return stock_item_out(item)
