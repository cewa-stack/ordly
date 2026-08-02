"""Testy jednostkowe InventoryService (IMS)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.entities.inventory_item import InventoryItem
from app.domain.exceptions.domain_exceptions import (
    DuplicateInventoryItemError,
    InsufficientStockError,
    InventoryItemNotFoundError,
)
from app.services.inventory_service import InventoryService
from tests.fakes.fake_inventory_repository import FakeInventoryRepository


@pytest.fixture
def repository() -> FakeInventoryRepository:
    return FakeInventoryRepository()


@pytest.fixture
def service(repository: FakeInventoryRepository) -> InventoryService:
    return InventoryService(repository)


async def test_create_item_starts_with_zero_stock(service: InventoryService) -> None:
    item = await service.create_item("PET60", "Butelka PET 60 ml")

    assert item.sku == "PET60"
    assert item.stock == 0
    assert item.min_stock == 0


async def test_create_duplicate_sku_raises(service: InventoryService) -> None:
    await service.create_item("PET60", "Butelka PET 60 ml")

    with pytest.raises(DuplicateInventoryItemError):
        await service.create_item("PET60", "Inna butelka")


async def test_set_stock_records_movement(
    service: InventoryService, repository: FakeInventoryRepository
) -> None:
    await service.create_item("PET60", "Butelka PET 60 ml")

    item = await service.set_stock("PET60", 500)

    assert item.stock == 500
    assert len(repository.movements) == 1
    movement = repository.movements[0]
    assert movement.change == 500
    assert movement.stock_after == 500
    assert movement.source == "manual"


async def test_add_and_remove_stock(
    service: InventoryService, repository: FakeInventoryRepository
) -> None:
    await service.create_item("PET60", "Butelka PET 60 ml")
    await service.set_stock("PET60", 100)

    after_add = await service.add_stock("PET60", 200)
    after_remove = await service.remove_stock("PET60", 15)

    assert after_add.stock == 300
    assert after_remove.stock == 285
    changes = [m.change for m in repository.movements]
    assert changes == [100, 200, -15]


async def test_remove_below_zero_raises(service: InventoryService) -> None:
    await service.create_item("PET60", "Butelka PET 60 ml")
    await service.set_stock("PET60", 10)

    with pytest.raises(InsufficientStockError):
        await service.remove_stock("PET60", 11)


async def test_unknown_sku_raises(service: InventoryService) -> None:
    with pytest.raises(InventoryItemNotFoundError):
        await service.set_stock("NOPE", 10)


async def test_negative_set_raises_value_error(service: InventoryService) -> None:
    await service.create_item("PET60", "Butelka PET 60 ml")

    with pytest.raises(ValueError):
        await service.set_stock("PET60", -5)


async def test_shopping_list_contains_low_stock_items(
    service: InventoryService,
) -> None:
    await service.create_item("PET60", "Butelka PET 60 ml")
    await service.set_stock("PET60", 100)
    await service.create_item("CAP", "Nakrętka czarna", min_stock=20)
    await service.set_stock("CAP", 7)

    shopping_list = await service.get_shopping_list()

    assert [item.sku for item in shopping_list] == ["CAP"]


async def test_report_totals_and_forecast(
    service: InventoryService, repository: FakeInventoryRepository
) -> None:
    repository.items["PET60"] = InventoryItem(
        sku="PET60",
        name="Butelka PET 60 ml",
        stock=240,
        min_stock=50,
        purchase_cost=Decimal("1.50"),
    )
    # 360 szt. sprzedane w oknie 30 dni -> 12 szt./dzień -> zapas na 20 dni
    await service.remove_stock("PET60", 1)  # ruch manualny, nie wpływa na prognozę
    from app.domain.entities.inventory_movement import (
        MOVEMENT_SOURCE_ORDER,
        InventoryMovement,
    )
    from app.utils.time import utc_now

    repository.movements.append(
        InventoryMovement(
            item_sku="PET60",
            item_name="Butelka PET 60 ml",
            change=-360,
            stock_after=239,
            reason="Nowe zamówienie",
            source=MOVEMENT_SOURCE_ORDER,
            reference="123",
            occurred_at=utc_now(),
        )
    )
    await service.set_stock("PET60", 240)

    report = await service.get_report()

    assert report.total_items == 1
    assert report.total_stock_value == Decimal("360.00")
    assert len(report.forecasts) == 1
    forecast = report.forecasts[0]
    assert forecast.avg_daily_sales == pytest.approx(12.0)
    assert forecast.days_left == 20
    assert report.items_without_sales == ()


async def test_report_marks_items_without_sales(service: InventoryService) -> None:
    await service.create_item("PET60", "Butelka PET 60 ml")

    report = await service.get_report()

    assert [i.sku for i in report.items_without_sales] == ["PET60"]
    assert report.forecasts == ()
