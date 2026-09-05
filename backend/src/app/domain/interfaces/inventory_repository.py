"""Abstrakcja dostępu do magazynu (IMS), niezależna od SQLite."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.inventory_movement import InventoryMovement
from app.domain.entities.offer_component import OfferComponent
from app.shared.dto.offer_mapping_dto import OfferRecipe


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
    async def delete(self, sku: str) -> None:
        """
        Usuwa produkt razem z jego historią ruchów i wypisuje go ze
        wszystkich receptur ofert; jego podprodukty tracą powiązanie
        z nim, ale zostają w magazynie.

        Raises:
            InventoryItemNotFoundError: Gdy produkt nie istnieje.
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
    async def get_sub_items(self, parent_sku: str) -> list[InventoryItem]:
        """
        Zwraca podprodukty przypisane do danego produktu głównego.

        Pusta lista, gdy produkt nie ma podproduktów albo w ogóle nie
        istnieje - to zapytanie o listę, nie o konkretny rekord.
        """
        raise NotImplementedError

    @abstractmethod
    async def set_parent(self, sku: str, parent_sku: str | None) -> None:
        """
        Ustawia lub czyści (parent_sku=None) produkt główny dla danego SKU.

        Repozytorium sprawdza wyłącznie istnienie obu produktów. Reguły
        biznesowe (brak samoprzypisania, jeden poziom zagnieżdżenia)
        pilnuje `InventoryService.set_parent`.

        Raises:
            InventoryItemNotFoundError: Gdy `sku` albo `parent_sku` nie istnieje.
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

    @abstractmethod
    async def get_all_offer_links(self) -> list[OfferRecipe]:
        """Zwraca wszystkie receptury ofert pogrupowane po ofercie."""
        raise NotImplementedError

    @abstractmethod
    async def replace_offer_links(
        self, marketplace: str, external_product_id: str, components: list[OfferComponent]
    ) -> None:
        """
        Zastępuje całą recepturę oferty podaną listą składników.

        Raises:
            InventoryItemNotFoundError: Gdy któreś SKU nie istnieje.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_movement_references(self, sku: str) -> set[str]:
        """
        Zwraca numery dokumentów, dla których produkt ma już zapisany
        ruch magazynowy (ochrona przed dwukrotną korektą wsteczną).
        """
        raise NotImplementedError
