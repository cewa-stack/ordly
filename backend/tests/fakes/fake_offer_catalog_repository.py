"""Fake implementacja OfferCatalogRepository - katalog ofert w pamięci."""

from __future__ import annotations

from datetime import datetime

from app.domain.entities.marketplace_offer import MarketplaceOffer
from app.domain.interfaces.offer_catalog_repository import OfferCatalogRepository


class FakeOfferCatalogRepository(OfferCatalogRepository):
    """Przechowuje katalog ofert w słowniku, kluczowanym parą (marketplace, id)."""

    def __init__(self) -> None:
        self.offers: dict[tuple[str, str], MarketplaceOffer] = {}

    async def replace_all(self, marketplace: str, offers: list[MarketplaceOffer]) -> int:
        for key in [k for k in self.offers if k[0] == marketplace]:
            del self.offers[key]
        for offer in offers:
            self.offers[(marketplace, offer.external_id)] = offer
        return len(offers)

    async def get_all(self, marketplace: str | None = None) -> list[MarketplaceOffer]:
        selected = [
            offer
            for (offer_marketplace, _), offer in self.offers.items()
            if marketplace is None or offer_marketplace == marketplace
        ]
        return sorted(selected, key=lambda o: o.name)

    async def get(self, marketplace: str, external_id: str) -> MarketplaceOffer | None:
        return self.offers.get((marketplace, external_id))

    async def last_synced_at(self, marketplace: str) -> datetime | None:
        stamps = [
            offer.synced_at
            for (offer_marketplace, _), offer in self.offers.items()
            if offer_marketplace == marketplace and offer.synced_at is not None
        ]
        return max(stamps) if stamps else None
