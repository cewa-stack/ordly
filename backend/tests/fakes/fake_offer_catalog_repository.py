"""Fake implementacja OfferCatalogRepository - katalog ofert w pamięci."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.domain.entities.marketplace_offer import MarketplaceOffer
from app.domain.entities.offer_stock_movement import OfferStockMovement
from app.domain.exceptions.domain_exceptions import OfferNotFoundError
from app.domain.interfaces.offer_catalog_repository import OfferCatalogRepository
from app.shared.dto.offer_catalog_dto import CatalogUpsertResult
from app.utils.time import utc_now


class FakeOfferCatalogRepository(OfferCatalogRepository):
    """Przechowuje katalog ofert w słowniku, kluczowanym parą (marketplace, id)."""

    def __init__(self) -> None:
        self.offers: dict[tuple[str, str], MarketplaceOffer] = {}
        self.history: dict[tuple[str, str], list[OfferStockMovement]] = {}

    async def upsert_all(
        self, marketplace: str, offers: list[MarketplaceOffer]
    ) -> CatalogUpsertResult:
        fetched_ids = {offer.external_id for offer in offers}
        stale = [k for k in self.offers if k[0] == marketplace and k[1] not in fetched_ids]
        for key in stale:
            del self.offers[key]
            self.history.pop(key, None)

        added = 0
        for offer in offers:
            key = (marketplace, offer.external_id)
            known = self.offers.get(key)
            if known is None:
                added += 1
            # Ręcznie wpisana ilość nie schodzi z API, więc przeżywa upsert.
            self.offers[key] = replace(
                offer,
                quantity_on_hand=known.quantity_on_hand if known else offer.quantity_on_hand,
            )

        return CatalogUpsertResult(added=added, removed=len(stale))

    async def get_all(self, marketplace: str | None = None) -> list[MarketplaceOffer]:
        selected = [
            offer
            for (offer_marketplace, _), offer in self.offers.items()
            if marketplace is None or offer_marketplace == marketplace
        ]
        return sorted(selected, key=lambda o: o.name)

    async def get(self, marketplace: str, external_id: str) -> MarketplaceOffer | None:
        return self.offers.get((marketplace, external_id))

    async def set_quantity(
        self, marketplace: str, external_id: str, quantity: int, reason: str
    ) -> MarketplaceOffer:
        key = (marketplace, external_id)
        offer = self.offers.get(key)
        if offer is None:
            raise OfferNotFoundError(marketplace, external_id)

        before = offer.quantity_on_hand or 0
        updated = replace(offer, quantity_on_hand=quantity)
        self.offers[key] = updated
        self.history.setdefault(key, []).insert(
            0,
            OfferStockMovement(
                change=quantity - before,
                quantity_after=quantity,
                reason=reason,
                occurred_at=utc_now(),
            ),
        )
        return updated

    async def get_history(
        self, marketplace: str, external_id: str, limit: int
    ) -> list[OfferStockMovement]:
        key = (marketplace, external_id)
        if key not in self.offers:
            raise OfferNotFoundError(marketplace, external_id)
        return self.history.get(key, [])[:limit]

    async def last_synced_at(self, marketplace: str) -> datetime | None:
        stamps = [
            offer.synced_at
            for (offer_marketplace, _), offer in self.offers.items()
            if offer_marketplace == marketplace and offer.synced_at is not None
        ]
        return max(stamps) if stamps else None
