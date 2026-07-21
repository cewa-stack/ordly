"""Testy jednostkowe ShippingReminderService - przypomnienie o wysyłce (20:00)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from app.domain.entities.customer import Customer
from app.domain.entities.order import Order
from app.domain.entities.product import Product
from app.domain.fulfillment import FULFILLMENT_NEW, FULFILLMENT_SENT
from app.services.shipping_reminder_service import ShippingReminderService
from tests.fakes.fake_order_repository import FakeOrderRepository

# 20:00 czasu Warszawy (lato, UTC+2) = 18:00 UTC. Początek doby warszawskiej
# to 22:00 UTC dnia poprzedniego - dzisiejsze zamówienia mają datę po tej granicy.
_NOW_UTC = datetime(2026, 7, 20, 18, 0, 0)
_TODAY_UTC = datetime(2026, 7, 20, 8, 0, 0)
_YESTERDAY_UTC = datetime(2026, 7, 19, 8, 0, 0)


def _make_order(
    external_id: str,
    order_date: datetime,
    fulfillment_status: str | None,
    status: str = "READY_FOR_PROCESSING",
) -> Order:
    return Order(
        external_id=external_id,
        marketplace="allegro",
        buyer=Customer(login="jan_kowalski"),
        products=[Product("PROD-1", "Olejek", 1, Decimal("29.99"))],
        total_amount=Decimal("29.99"),
        currency="PLN",
        status=status,
        order_date=order_date,
        fulfillment_status=fulfillment_status,
    )


@pytest.fixture
def repository() -> FakeOrderRepository:
    return FakeOrderRepository()


@pytest.fixture
def service(repository: FakeOrderRepository) -> ShippingReminderService:
    return ShippingReminderService(repository)


async def test_no_orders_today_returns_none(
    service: ShippingReminderService, repository: FakeOrderRepository
) -> None:
    await repository.save(_make_order("OLD-1", _YESTERDAY_UTC, FULFILLMENT_NEW))

    result = await service.build_reminder(now=_NOW_UTC)

    assert result is None


async def test_all_today_orders_shipped_returns_none(
    service: ShippingReminderService, repository: FakeOrderRepository
) -> None:
    await repository.save(_make_order("A", _TODAY_UTC, FULFILLMENT_SENT))
    await repository.save(_make_order("B", _TODAY_UTC, FULFILLMENT_SENT))

    result = await service.build_reminder(now=_NOW_UTC)

    assert result is None


async def test_unshipped_orders_are_reported(
    service: ShippingReminderService, repository: FakeOrderRepository
) -> None:
    await repository.save(_make_order("A", _TODAY_UTC, FULFILLMENT_SENT))
    await repository.save(_make_order("B", _TODAY_UTC, FULFILLMENT_NEW))
    await repository.save(_make_order("C", _TODAY_UTC, None))

    result = await service.build_reminder(now=_NOW_UTC)

    assert result is not None
    assert result.orders_today == 3
    assert result.unshipped_count == 2
    unshipped_ids = {o.external_id for o in result.unshipped_orders}
    assert unshipped_ids == {"B", "C"}


async def test_cancelled_order_is_not_counted_as_unshipped(
    service: ShippingReminderService, repository: FakeOrderRepository
) -> None:
    await repository.save(
        _make_order("CANCELLED", _TODAY_UTC, FULFILLMENT_NEW, status="CANCELLED")
    )
    await repository.save(_make_order("PENDING", _TODAY_UTC, FULFILLMENT_NEW))

    result = await service.build_reminder(now=_NOW_UTC)

    assert result is not None
    assert result.unshipped_count == 1
    assert result.unshipped_orders[0].external_id == "PENDING"
