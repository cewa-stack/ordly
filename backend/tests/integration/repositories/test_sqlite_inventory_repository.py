"""Testy integracyjne SqliteInventoryRepository na bazie SQLite in-memory."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.inventory_movement import (
    MOVEMENT_SOURCE_MANUAL,
    MOVEMENT_SOURCE_ORDER,
    InventoryMovement,
)
from app.domain.exceptions.domain_exceptions import (
    DuplicateInventoryItemError,
    InventoryItemNotFoundError,
)
from app.repositories.sqlite_inventory_repository import SqliteInventoryRepository
from app.repositories.sqlite_stock_sync_repository import SqliteStockSyncRepository
from app.utils.time import utc_now


@pytest.fixture
def repository(in_memory_session: AsyncSession) -> SqliteInventoryRepository:
    return SqliteInventoryRepository(in_memory_session)


def _make_item(sku: str = "PET60", **overrides: object) -> InventoryItem:
    defaults: dict = {
        "sku": sku,
        "name": "Butelka PET 60 ml",
        "stock": 100,
        "min_stock": 20,
        "purchase_cost": Decimal("1.50"),
    }
    defaults.update(overrides)
    return InventoryItem(**defaults)


async def test_create_and_get_by_sku(repository: SqliteInventoryRepository) -> None:
    await repository.create(_make_item())

    item = await repository.get_by_sku("PET60")

    assert item is not None
    assert item.name == "Butelka PET 60 ml"
    assert item.stock == 100
    assert item.purchase_cost == Decimal("1.50")


async def test_create_duplicate_sku_raises(
    repository: SqliteInventoryRepository,
) -> None:
    await repository.create(_make_item())

    with pytest.raises(DuplicateInventoryItemError):
        await repository.create(_make_item(name="Inna butelka"))


async def test_set_stock_and_min_stock(
    repository: SqliteInventoryRepository,
) -> None:
    await repository.create(_make_item())

    await repository.set_stock("PET60", 55)
    await repository.set_min_stock("PET60", 60)

    item = await repository.get_by_sku("PET60")
    assert item is not None
    assert item.stock == 55
    assert item.min_stock == 60


async def test_set_stock_unknown_sku_raises(
    repository: SqliteInventoryRepository,
) -> None:
    with pytest.raises(InventoryItemNotFoundError):
        await repository.set_stock("NOPE", 10)


async def test_movements_are_recorded_and_filtered(
    repository: SqliteInventoryRepository,
) -> None:
    await repository.create(_make_item("PET60"))
    await repository.create(_make_item("CAP", name="Nakrętka"))
    now = utc_now()
    await repository.record_movement(
        InventoryMovement(
            item_sku="PET60",
            item_name="Butelka PET 60 ml",
            change=-2,
            stock_after=98,
            reason="Nowe zamówienie",
            source=MOVEMENT_SOURCE_ORDER,
            reference="ORDER-1",
            occurred_at=now,
        )
    )
    await repository.record_movement(
        InventoryMovement(
            item_sku="CAP",
            item_name="Nakrętka",
            change=500,
            stock_after=600,
            reason="Dostawa od hurtowni",
            source=MOVEMENT_SOURCE_MANUAL,
            reference=None,
            occurred_at=now,
        )
    )

    all_movements = await repository.get_movements(None, limit=10)
    pet_movements = await repository.get_movements("PET60", limit=10)

    assert len(all_movements) == 2
    assert [m.item_sku for m in pet_movements] == ["PET60"]
    assert pet_movements[0].reference == "ORDER-1"


async def test_get_low_stock(repository: SqliteInventoryRepository) -> None:
    await repository.create(_make_item("PET60", stock=100, min_stock=20))
    await repository.create(_make_item("CAP", name="Nakrętka", stock=7, min_stock=20))

    low = await repository.get_low_stock()

    assert [item.sku for item in low] == ["CAP"]


async def test_get_sales_since_sums_order_movements(
    repository: SqliteInventoryRepository,
) -> None:
    await repository.create(_make_item("PET60"))
    now = utc_now()
    for change, occurred in ((-2, now), (-3, now), (-5, now - timedelta(days=60))):
        await repository.record_movement(
            InventoryMovement(
                item_sku="PET60",
                item_name="Butelka PET 60 ml",
                change=change,
                stock_after=100,
                reason="Nowe zamówienie",
                source=MOVEMENT_SOURCE_ORDER,
                reference="ORDER-1",
                occurred_at=occurred,
            )
        )

    sales = await repository.get_sales_since(now - timedelta(days=30))

    assert sales == {"PET60": 5}


async def test_offer_links_roundtrip(repository: SqliteInventoryRepository) -> None:
    await repository.create(_make_item("PET60"))
    await repository.create(_make_item("CAP", name="Nakrętka"))
    await repository.add_offer_link("allegro", "KIT-1", "PET60", 2)
    await repository.add_offer_link("allegro", "KIT-1", "CAP", 2)

    links = await repository.get_offer_links("allegro", "KIT-1")
    removed = await repository.remove_offer_links("allegro", "KIT-1")
    links_after = await repository.get_offer_links("allegro", "KIT-1")

    assert {(link.sku, link.quantity) for link in links} == {("PET60", 2), ("CAP", 2)}
    assert removed == 2
    assert links_after == []


async def test_stock_sync_markers_are_unique(
    in_memory_session: AsyncSession,
) -> None:
    repository = SqliteStockSyncRepository(in_memory_session)

    first = await repository.mark_processed("allegro", "ORDER-1", "DEDUCT")
    second = await repository.mark_processed("allegro", "ORDER-1", "DEDUCT")
    other = await repository.mark_processed("allegro", "ORDER-1", "RESTORE_CANCEL")

    assert first is True
    assert second is False
    assert other is True
    assert await repository.was_processed("allegro", "ORDER-1", "DEDUCT") is True
    assert await repository.was_processed("allegro", "ORDER-2", "DEDUCT") is False
