"""Kontrakt repozytorium katalogu ofert marketplace."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.entities.marketplace_offer import MarketplaceOffer


class OfferCatalogRepository(ABC):
    """Przechowuje lokalną kopię asortymentu wystawionego na marketplace."""

    @abstractmethod
    async def replace_all(self, marketplace: str, offers: list[MarketplaceOffer]) -> int:
        """
        Zastępuje cały katalog danego marketplace pobraną listą ofert.

        Pełna podmiana, a nie dopisywanie: oferta usunięta z Allegro ma
        zniknąć również z listy do powiązania, inaczej katalog puchłby
        o martwe pozycje bez żadnego sygnału, że ich już nie ma.

        Returns:
            Liczba zapisanych ofert.
        """

    @abstractmethod
    async def get_all(self, marketplace: str | None = None) -> list[MarketplaceOffer]:
        """Zwraca katalog ofert, opcjonalnie zawężony do jednego marketplace."""

    @abstractmethod
    async def get(self, marketplace: str, external_id: str) -> MarketplaceOffer | None:
        """Zwraca jedną ofertę katalogu albo None, gdy jej nie ma."""

    @abstractmethod
    async def last_synced_at(self, marketplace: str) -> datetime | None:
        """Zwraca moment ostatniej udanej synchronizacji katalogu."""
