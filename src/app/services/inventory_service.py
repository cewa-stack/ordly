"""
Serwis magazynowy (Inventory Management System) - centralny magazyn TOOM.

Obsługuje przegląd stanów, ręczne korekty z pełną historią zmian,
listę zakupów, prognozę wyczerpania zapasów oraz raport magazynowy.
Zmiany automatyczne (sprzedaż, zwroty, anulowania) wykonuje osobny
StockSyncService - oba serwisy piszą do tej samej historii ruchów.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.inventory_movement import (
    MOVEMENT_SOURCE_MANUAL,
    InventoryMovement,
)
from app.domain.exceptions.domain_exceptions import (
    InsufficientStockError,
    InventoryItemNotFoundError,
)
from app.domain.interfaces.inventory_repository import InventoryRepository
from app.shared.dto.inventory_dto import InventoryReport, ItemForecast
from app.utils.time import utc_now

_FORECAST_WINDOW_DAYS = 30


class InventoryService:
    """Logika biznesowa centralnego magazynu (komendy /stock)."""

    def __init__(self, inventory_repository: InventoryRepository) -> None:
        """
        Args:
            inventory_repository: Repozytorium dostępu do magazynu.
        """
        self._repository = inventory_repository

    async def get_stock_overview(self) -> list[InventoryItem]:
        """Zwraca wszystkie produkty magazynowe (komenda /stock)."""
        return await self._repository.get_all()

    async def get_item(self, sku: str) -> InventoryItem:
        """
        Zwraca pojedynczy produkt magazynowy po SKU (ekran szczegółów w
        aplikacji mobilnej).

        Raises:
            InventoryItemNotFoundError: Gdy produkt nie istnieje.
        """
        return await self._require_item(sku)

    async def create_item(
        self, sku: str, name: str, min_stock: int = 0
    ) -> InventoryItem:
        """
        Tworzy nowy produkt magazynowy ze stanem początkowym 0.

        Raises:
            DuplicateInventoryItemError: Gdy SKU już istnieje.
        """
        item = InventoryItem(sku=sku, name=name, stock=0, min_stock=min_stock)
        await self._repository.create(item)
        return item

    async def set_stock(
        self, sku: str, quantity: int, reason: str = "Korekta magazynowa"
    ) -> InventoryItem:
        """
        Ustawia stan magazynowy na podaną wartość (komenda /stock set).

        Raises:
            InventoryItemNotFoundError: Gdy produkt nie istnieje.
            ValueError: Gdy podano ujemną ilość.
        """
        if quantity < 0:
            raise ValueError("Stan magazynowy nie może być ujemny")

        item = await self._require_item(sku)
        return await self._apply_change(item, quantity - item.stock, reason)

    async def add_stock(
        self, sku: str, quantity: int, reason: str = "Dostawa"
    ) -> InventoryItem:
        """
        Zwiększa stan magazynowy (komenda /stock add).

        Raises:
            InventoryItemNotFoundError: Gdy produkt nie istnieje.
            ValueError: Gdy podano ilość mniejszą od 1.
        """
        if quantity < 1:
            raise ValueError("Ilość musi być większa od zera")

        item = await self._require_item(sku)
        return await self._apply_change(item, quantity, reason)

    async def remove_stock(
        self, sku: str, quantity: int, reason: str = "Korekta magazynowa"
    ) -> InventoryItem:
        """
        Zmniejsza stan magazynowy (komenda /stock remove).

        Raises:
            InventoryItemNotFoundError: Gdy produkt nie istnieje.
            InsufficientStockError: Gdy stan spadłby poniżej zera.
            ValueError: Gdy podano ilość mniejszą od 1.
        """
        if quantity < 1:
            raise ValueError("Ilość musi być większa od zera")

        item = await self._require_item(sku)
        if item.stock - quantity < 0:
            raise InsufficientStockError(sku, quantity, item.stock)
        return await self._apply_change(item, -quantity, reason)

    async def set_min_stock(self, sku: str, min_stock: int) -> InventoryItem:
        """
        Ustawia minimalny stan magazynowy (próg ostrzeżeń i listy zakupów).

        Raises:
            InventoryItemNotFoundError: Gdy produkt nie istnieje.
            ValueError: Gdy podano ujemną wartość.
        """
        if min_stock < 0:
            raise ValueError("Minimalny stan nie może być ujemny")

        item = await self._require_item(sku)
        await self._repository.set_min_stock(sku, min_stock)
        return replace(item, min_stock=min_stock)

    async def get_history(
        self, sku: str | None = None, limit: int = 10
    ) -> list[InventoryMovement]:
        """Zwraca historię zmian magazynowych (komenda /stock history)."""
        return await self._repository.get_movements(sku, limit)

    async def get_shopping_list(self) -> list[InventoryItem]:
        """
        Zwraca listę zakupów - produkty, które osiągnęły minimalny stan
        magazynowy (komenda /stock buy).
        """
        return await self._repository.get_low_stock()

    async def link_offer(
        self, marketplace: str, external_product_id: str, sku: str, quantity: int
    ) -> None:
        """
        Przypisuje produkt magazynowy jako składnik oferty marketplace
        (obsługa zestawów wieloskładnikowych).

        Raises:
            InventoryItemNotFoundError: Gdy produkt o danym SKU nie istnieje.
            ValueError: Gdy podano ilość mniejszą od 1.
        """
        if quantity < 1:
            raise ValueError("Ilość składnika musi być większa od zera")
        await self._repository.add_offer_link(
            marketplace, external_product_id, sku, quantity
        )

    async def unlink_offer(self, marketplace: str, external_product_id: str) -> int:
        """Usuwa mapowanie oferty marketplace. Zwraca liczbę usuniętych składników."""
        return await self._repository.remove_offer_links(
            marketplace, external_product_id
        )

    async def get_report(self) -> InventoryReport:
        """
        Buduje pełny raport magazynowy (komenda /stock report):
        liczba produktów, wartość magazynu, niskie stany, produkty bez
        sprzedaży, prognozy wyczerpania i ostatnia historia zmian.
        """
        items = await self._repository.get_all()
        since = utc_now() - timedelta(days=_FORECAST_WINDOW_DAYS)
        sales = await self._repository.get_sales_since(since)

        total_value = sum(
            (item.stock_value for item in items), start=Decimal("0")
        )
        low_stock = tuple(item for item in items if item.is_low_stock)
        without_sales = tuple(item for item in items if item.sku not in sales)

        forecasts = []
        for item in items:
            sold = sales.get(item.sku, 0)
            if sold <= 0:
                continue
            avg_daily = sold / _FORECAST_WINDOW_DAYS
            forecasts.append(
                ItemForecast(
                    sku=item.sku,
                    name=item.name,
                    stock=item.stock,
                    avg_daily_sales=avg_daily,
                    days_left=int(item.stock / avg_daily),
                )
            )
        forecasts.sort(key=lambda f: f.days_left)

        recent_movements = await self._repository.get_movements(None, limit=10)

        return InventoryReport(
            total_items=len(items),
            total_stock_value=total_value,
            low_stock_items=low_stock,
            items_without_sales=without_sales,
            forecasts=tuple(forecasts),
            recent_movements=tuple(recent_movements),
        )

    async def _require_item(self, sku: str) -> InventoryItem:
        """Zwraca produkt po SKU lub rzuca InventoryItemNotFoundError."""
        item = await self._repository.get_by_sku(sku)
        if item is None:
            raise InventoryItemNotFoundError(sku)
        return item

    async def _apply_change(
        self, item: InventoryItem, change: int, reason: str
    ) -> InventoryItem:
        """Utrwala zmianę stanu wraz z wpisem w historii ruchów."""
        new_stock = item.stock + change
        await self._repository.set_stock(item.sku, new_stock)
        await self._repository.record_movement(
            InventoryMovement(
                item_sku=item.sku,
                item_name=item.name,
                change=change,
                stock_after=new_stock,
                reason=reason,
                source=MOVEMENT_SOURCE_MANUAL,
                reference=None,
                occurred_at=utc_now(),
            )
        )
        return replace(item, stock=new_stock)
