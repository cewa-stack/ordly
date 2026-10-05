"""
Endpointy HTTP /api/v1/hub/wholesale/* - hurtownie dla ORDLy Control Hub.

Hurtownie i szablony maili edytuje się na desktopie (pliki w katalogu
aplikacji). Desktop wysyła tu ich kopię po każdej zmianie i przy starcie,
bo Hub rozmawia tylko z Pi. Drugi endpoint oddaje desktopowi zamówienia
wysłane z Huba, żeby trafiły do historii na ekranie Hurtownia.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_container
from app.api.schemas import HubWholesaleCatalogIn, HubWholesaleCatalogOut, HubWholesaleOrderOut
from app.container import Container

router = APIRouter()


@router.put("/hub/wholesale/catalog", response_model=HubWholesaleCatalogOut)
async def put_wholesale_catalog(
    container: Annotated[Container, Depends(get_container)],
    payload: HubWholesaleCatalogIn,
) -> HubWholesaleCatalogOut:
    """Zastępuje kopię hurtowni i szablonów na Pi tym, co ma desktop."""
    version = await container.hub_wholesale.save_catalog(payload.model_dump(exclude_none=True))
    return HubWholesaleCatalogOut(
        version=version,
        wholesalers=len(payload.wholesalers),
        templates=len(payload.templates),
    )


@router.get("/hub/wholesale/orders", response_model=list[HubWholesaleOrderOut])
async def list_wholesale_orders(
    container: Annotated[Container, Depends(get_container)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[HubWholesaleOrderOut]:
    """Zamówienia do hurtowni wysłane z Huba, od najnowszego."""
    orders = await container.hub_wholesale.list_sent_orders(limit)
    return [
        HubWholesaleOrderOut(
            request_id=order.request_id,
            wholesaler_id=order.wholesaler_id,
            wholesaler_name=order.wholesaler_name,
            sent_at=order.sent_at,
            subject=order.subject,
            items_summary=order.items_summary,
            test_mode=order.test_mode,
        )
        for order in orders
        if order.sent_at is not None
    ]
