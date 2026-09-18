"""Kontrakt repozytorium katalogu ofert marketplace."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.entities.marketplace_offer import MarketplaceOffer
from app.domain.entities.offer_stock_movement import OfferStockMovement
from app.shared.dto.offer_catalog_dto import CatalogUpsertResult


class OfferCatalogRepository(ABC):
    """Przechowuje lokalną kopię asortymentu wystawionego na marketplace."""

    @abstractmethod
    async def upsert_all(
        self, marketplace: str, offers: list[MarketplaceOffer]
    ) -> CatalogUpsertResult:
        """
        Dosuwa katalog danego marketplace do pobranej listy ofert.

        Oferty już znane dostają świeże dane z API, nowe dochodzą,
        a te, których w liście nie ma, znikają razem z historią ilości -
        oferta zdjęta z Allegro ma zniknąć też tutaj, inaczej katalog
        puchłby o martwe pozycje bez sygnału, że ich już nie ma.

        Ręcznie wpisana ilość (`quantity_on_hand`) przeżywa
        synchronizację. Pobrana lista jej nie zawiera, więc nadpisanie
        całego wiersza kasowałoby jedyną liczbę w tej tabeli, której
        nie da się odtworzyć z marketplace.

        Returns:
            Ile ofert doszło i ile zniknęło.
        """

    @abstractmethod
    async def get_all(self, marketplace: str | None = None) -> list[MarketplaceOffer]:
        """Zwraca katalog ofert, opcjonalnie zawężony do jednego marketplace."""

    @abstractmethod
    async def get(self, marketplace: str, external_id: str) -> MarketplaceOffer | None:
        """Zwraca jedną ofertę katalogu albo None, gdy jej nie ma."""

    @abstractmethod
    async def set_quantity(
        self, marketplace: str, external_id: str, quantity: int, reason: str
    ) -> MarketplaceOffer:
        """
        Zapisuje ręcznie wpisaną ilość i dokłada wpis do historii.

        Raises:
            OfferNotFoundError: Gdy oferty nie ma w katalogu.
        """

    @abstractmethod
    async def get_history(
        self, marketplace: str, external_id: str, limit: int
    ) -> list[OfferStockMovement]:
        """Zwraca historię ręcznych zmian ilości, od najnowszej."""

    @abstractmethod
    async def last_synced_at(self, marketplace: str) -> datetime | None:
        """Zwraca moment ostatniej udanej synchronizacji katalogu."""
