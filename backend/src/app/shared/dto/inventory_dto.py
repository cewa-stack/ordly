"""DTO modułu magazynowego - raport, prognoza i wynik synchronizacji stanów."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.inventory_movement import InventoryMovement


@dataclass(frozen=True, slots=True)
class ItemForecast:
    """Prognoza wyczerpania zapasów dla jednego produktu."""

    sku: str
    name: str
    stock: int
    avg_daily_sales: float
    days_left: int


@dataclass(frozen=True, slots=True)
class InventoryReport:
    """Raport magazynowy generowany przez komendę /stock report."""

    total_items: int
    total_stock_value: Decimal
    low_stock_items: tuple[InventoryItem, ...] = field(default_factory=tuple)
    items_without_sales: tuple[InventoryItem, ...] = field(default_factory=tuple)
    forecasts: tuple[ItemForecast, ...] = field(default_factory=tuple)
    recent_movements: tuple[InventoryMovement, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class StockSyncOutcome:
    """
    Wynik jednej operacji automatycznej synchronizacji stanów.

    `processed=False` oznacza, że operacja została pominięta przez
    ochronę przed podwójnym odjęciem (znacznik synchronizacji istniał).
    """

    processed: bool
    operation: str
    reference: str
    low_stock_items: tuple[InventoryItem, ...] = field(default_factory=tuple)
    unmatched_products: tuple[str, ...] = field(default_factory=tuple)
