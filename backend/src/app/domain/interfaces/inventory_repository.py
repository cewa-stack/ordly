"""Abstrakcja dostępu do magazynu (IMS), niezależna od SQLite."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.inventory_movement import InventoryMovement
from app.domain.entities.offer_component import OfferComponent


class InventoryRepository(ABC):
    """
    Kontrakt dostępu do produktów magazynowych, historii ruchów
    oraz mapowań ofert marketplace na produkty magazynowe.
    """

    @abstractmethod
    async def get_all(self) -> list[InventoryItem]:
        """Zwraca wszystkie produkty magazynowe posortowane po nazwie."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_sku(self, sku: str) -> InventoryItem | None:
        """Zwraca produkt po SKU lub None, gdy nie istnieje."""
        raise NotImplementedError

    @abstractmethod
    async def create(self, item: InventoryItem) -> None:
        """
        Tworzy nowy produkt magazynowy.

        Raises:
            DuplicateInventoryItemError: Gdy SKU już istnieje.
        """
        raise NotImplementedError

    @abstractmethod
    async def set_stock(self, sku: str, new_stock: int) -> None:
        """
        Ustawia stan magazynowy produktu.

        Raises:
            InventoryItemNotFoundError: Gdy produkt nie istnieje.
        """
        raise NotImplementedError

    @abstractmethod
    async def set_min_stock(self, sku: str, min_stock: int) -> None:
        """
        Ustawia minimalny stan magazynowy produktu.

        Raises:
            InventoryItemNotFoundError: Gdy produkt nie istnieje.
        """
        raise NotImplementedError

    @abstractmethod
    async def record_movement(self, movement: InventoryMovement) -> None:
        """Zapisuje ruch magazynowy w historii zmian."""
        raise NotImplementedError

    @abstractmethod
    async def get_movements(
        self, sku: str | None = None, limit: int = 10
    ) -> list[InventoryMovement]:
        """Zwraca ostatnie ruchy magazynowe (opcjonalnie dla jednego SKU)."""
        raise NotImplementedError

    @abstractmethod
    async def get_low_stock(self) -> list[InventoryItem]:
        """Zwraca produkty, które osiągnęły minimalny stan magazynowy."""
        raise NotImplementedError

    @abstractmethod
    async def get_sales_since(self, since: datetime) -> dict[str, int]:
        """
        Zwraca mapę SKU -> liczba sztuk sprzedanych od podanej daty
        (na podstawie ruchów magazynowych o źródle 'order').
        """
        raise NotImplementedError

    @abstractmethod
    async def get_offer_links(
        self, marketplace: str, external_product_id: str
    ) -> list[OfferComponent]:
        """Zwraca składniki magazynowe przypisane do oferty marketplace."""
        raise NotImplementedError

    @abstractmethod
    async def add_offer_link(
        self, marketplace: str, external_product_id: str, sku: str, quantity: int
    ) -> None:
        """
        Przypisuje produkt magazynowy jako składnik oferty marketplace.

        Raises:
            InventoryItemNotFoundError: Gdy produkt o danym SKU nie istnieje.
        """
        raise NotImplementedError

    @abstractmethod
    async def remove_offer_links(self, marketplace: str, external_product_id: str) -> int:
        """Usuwa wszystkie składniki oferty. Zwraca liczbę usuniętych wpisów."""
        raise NotImplementedError
