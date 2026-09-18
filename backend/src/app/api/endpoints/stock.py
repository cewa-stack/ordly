"""
Endpointy HTTP /api/v1/stock/* - magazyn ORDLY, czyli lista ofert
wystawionych na marketplace i ręcznie wpisana ilość przy każdej.

DLACZEGO `{external_id:path}`, A NIE `{external_id}`. Identyfikator
oferty potrafi zawierać ukośnik, a serwer ASGI dekoduje `%2F` ze
ścieżki ZANIM router cokolwiek dopasuje (uvicorn: `unquote(raw_path)`).
Żądanie `/stock/offers/allegro/A%2FB/quantity` dociera więc do routera
jako `/stock/offers/allegro/A/B/quantity` i przy zwykłym `{external_id}`
(wzorzec `[^/]+`) nie pasuje do żadnej trasy - spada do
`StaticFiles("/")`, który serwuje PWA i na PUT odpowiada `405 Method
Not Allowed`. W interfejsie wyglądało to jak awaria zapisu ilości
wyłącznie dla części ofert. `{external_id:path}` kompiluje się do `.*`,
więc ukośnik zostaje częścią identyfikatora.

Kolejność tras jest przez to KRYTYCZNA, a nie tylko porządkowa:
`.*` połyka wszystko, co pasuje, więc trasy z literałem na końcu
(`/quantity`, `/history`) muszą stać niżej niż literały
(`/stock/offers`, `/stock/sync`), ale żadna trasa nie może kończyć się
gołym `{external_id:path}` nad nimi. `tests/integration/api/
test_stock_slash_sku.py` pilnuje właśnie tego.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_container, get_session
from app.api.schemas import (
    CatalogSyncOut,
    OfferMovementOut,
    OfferOut,
    OfferQuantityIn,
    catalog_sync_out,
    offer_movement_out,
    offer_out,
)
from app.container import Container
from app.services.offer_catalog_service import DEFAULT_HISTORY_LIMIT

router = APIRouter()


@router.get("/stock/offers", response_model=list[OfferOut])
async def list_offers(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[OfferOut]:
    """Zwraca oferty wystawione na marketplace razem z ilościami na półce."""
    service = container.offer_catalog_service(session)
    return [offer_out(offer) for offer in await service.get_offers()]


@router.post("/stock/sync", response_model=CatalogSyncOut)
async def sync_offers(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CatalogSyncOut:
    """
    Pobiera asortyment z marketplace i dosuwa do niego lokalny katalog.

    Ręcznie wpisane ilości zostają nietknięte - marketplace ich nie zna,
    więc nie ma ich czym nadpisać.
    """
    service = container.offer_catalog_service(session)
    return catalog_sync_out(await service.sync())


@router.put(
    "/stock/offers/{marketplace}/{external_id:path}/quantity", response_model=OfferOut
)
async def set_offer_quantity(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    marketplace: str,
    external_id: str,
    payload: OfferQuantityIn,
) -> OfferOut:
    """Zapisuje ręcznie policzoną ilość przy ofercie i dokłada wpis historii."""
    service = container.offer_catalog_service(session)
    offer = await service.set_quantity(
        marketplace, external_id, payload.quantity, payload.reason
    )
    return offer_out(offer)


@router.get(
    "/stock/offers/{marketplace}/{external_id:path}/history",
    response_model=list[OfferMovementOut],
)
async def get_offer_history(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    marketplace: str,
    external_id: str,
    limit: Annotated[int, Query(ge=1, le=100)] = DEFAULT_HISTORY_LIMIT,
) -> list[OfferMovementOut]:
    """Historia ręcznych zmian ilości dla jednej oferty, od najnowszej."""
    service = container.offer_catalog_service(session)
    movements = await service.get_history(marketplace, external_id, limit)
    return [offer_movement_out(movement) for movement in movements]
