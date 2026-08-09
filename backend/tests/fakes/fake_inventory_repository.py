"""Fake implementacja InventoryRepository - magazyn w pamięci do testów."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.inventory_movement import (
    MOVEMENT_SOURCE_ORDER,
    InventoryMovement,
)
from app.domain.entities.offer_component import OfferComponent
from app.domain.exceptions.domain_exceptions import (
    DuplicateInventoryItemError,
    InventoryItemNotFoundError,
)
from app.domain.interfaces.inventory_repository import InventoryRepository
from app.shared.dto.offer_mapping_dto import OfferRecipe, RecipeComponent


class FakeInventoryRepository(InventoryRepository):
    """Przechowuje produkty, ruchy i mapowania ofert w słownikach."""

    def __init__(self) -> None:
        self.items: dict[str, InventoryItem] = {}
        self.movements: list[InventoryMovement] = []
        self.links: dict[tuple[str, str], list[OfferComponent]] = {}

    async def get_all(self) -> list[InventoryItem]:
        return sorted(self.items.values(), key=lambda i: i.name)

    async def get_by_sku(self, sku: str) -> InventoryItem | None:
        return self.items.get(sku)

    async def create(self, item: InventoryItem) -> None:
        if item.sku in self.items:
            raise DuplicateInventoryItemError(item.sku)
        self.items[item.sku] = item

    async def set_stock(self, sku: str, new_stock: int) -> None:
        if sku not in self.items:
            raise InventoryItemNotFoundError(sku)
        self.items[sku] = replace(self.items[sku], stock=new_stock)

    async def set_min_stock(self, sku: str, min_stock: int) -> None:
        if sku not in self.items:
            raise InventoryItemNotFoundError(sku)
        self.items[sku] = replace(self.items[sku], min_stock=min_stock)

    async def record_movement(self, movement: InventoryMovement) -> None:
        if movement.item_sku not in self.items:
            raise InventoryItemNotFoundError(movement.item_sku)
        self.movements.append(movement)

    async def get_movements(
        self, sku: str | None = None, limit: int = 10
    ) -> list[InventoryMovement]:
        movements = [m for m in self.movements if sku is None or m.item_sku == sku]
        movements.sort(key=lambda m: m.occurred_at, reverse=True)
        return movements[:limit]

    async def get_low_stock(self) -> list[InventoryItem]:
        return [i for i in self.items.values() if i.is_low_stock]

    async def get_sales_since(self, since: datetime) -> dict[str, int]:
        sales: dict[str, int] = {}
        for movement in self.movements:
            if (
                movement.source == MOVEMENT_SOURCE_ORDER
                and movement.change < 0
                and movement.occurred_at >= since
            ):
                sales[movement.item_sku] = sales.get(movement.item_sku, 0) - movement.change
        return sales

    async def get_offer_links(
        self, marketplace: str, external_product_id: str
    ) -> list[OfferComponent]:
        return list(self.links.get((marketplace, external_product_id), []))

    async def add_offer_link(
        self, marketplace: str, external_product_id: str, sku: str, quantity: int
    ) -> None:
        if sku not in self.items:
            raise InventoryItemNotFoundError(sku)
        components = self.links.setdefault((marketplace, external_product_id), [])
        for index, existing in enumerate(components):
            if existing.sku == sku:
                components[index] = OfferComponent(sku=sku, quantity=quantity)
                return
        components.append(OfferComponent(sku=sku, quantity=quantity))

    async def remove_offer_links(self, marketplace: str, external_product_id: str) -> int:
        removed = self.links.pop((marketplace, external_product_id), [])
        return len(removed)

    async def get_all_offer_links(self) -> list[OfferRecipe]:
        return [
            OfferRecipe(
                marketplace=marketplace,
                external_product_id=external_product_id,
                offer_name=None,
                components=tuple(
                    RecipeComponent(
                        sku=component.sku,
                        name=self.items[component.sku].name,
                        quantity=component.quantity,
                    )
                    for component in components
                    if component.sku in self.items
                ),
            )
            for (marketplace, external_product_id), components in self.links.items()
        ]

    async def replace_offer_links(
        self, marketplace: str, external_product_id: str, components: list[OfferComponent]
    ) -> None:
        for component in components:
            if component.sku not in self.items:
                raise InventoryItemNotFoundError(component.sku)
        self.links[(marketplace, external_product_id)] = list(components)

    async def get_movement_references(self, sku: str) -> set[str]:
        return {
            movement.reference
            for movement in self.movements
            if movement.item_sku == sku and movement.reference
        }
