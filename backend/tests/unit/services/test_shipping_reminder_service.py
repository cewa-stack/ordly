"""Testy jednostkowe ShippingReminderService - przypomnienie o statusie NEW (20:00)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from app.domain.entities.customer import Customer
from app.domain.entities.order import Order
from app.domain.entities.product import Product
from app.domain.fulfillment import (
    FULFILLMENT_NEW,
    FULFILLMENT_PROCESSING,
    FULFILLMENT_READY_FOR_SHIPMENT,
    FULFILLMENT_SENT,
)
from app.services.shipping_reminder_service import ShippingReminderService
from tests.fakes.fake_order_repository import FakeOrderRepository

_TODAY_UTC = datetime(2026, 7, 20, 8, 0, 0)
_LAST_WEEK_UTC = datetime(2026, 7, 13, 8, 0, 0)


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


async def test_no_orders_at_all_returns_none(
    service: ShippingReminderService,
) -> None:
    result = await service.build_reminder()

    assert result is None


async def test_only_processing_and_sent_orders_returns_none(
    service: ShippingReminderService, repository: FakeOrderRepository
) -> None:
    await repository.save(_make_order("A", _TODAY_UTC, FULFILLMENT_SENT))
    await repository.save(_make_order("B", _TODAY_UTC, FULFILLMENT_PROCESSING))

    result = await service.build_reminder()

    assert result is None


async def test_ready_for_shipment_order_returns_none(
    service: ShippingReminderService, repository: FakeOrderRepository
) -> None:
    """Spakowane, czekające na kuriera zamówienie nie wymaga nagania."""
    await repository.save(_make_order("READY", _TODAY_UTC, FULFILLMENT_READY_FOR_SHIPMENT))

    result = await service.build_reminder()

    assert result is None


async def test_order_without_known_fulfillment_stage_returns_none(
    service: ShippingReminderService, repository: FakeOrderRepository
) -> None:
    """
    NULL to "etapu nigdy nie pobrano z marketplace", nie "nowe".

    Takie wiersze zostają po zamówieniach, których Allegro nie zwraca już
    w synchronizacji - bez tego wykluczenia przypomnienie 20:00
    przychodziło o nich codziennie, w nieskończoność.
    """
    await repository.save(_make_order("STARE-BEZ-ETAPU", _LAST_WEEK_UTC, None))

    result = await service.build_reminder()

    assert result is None


async def test_new_status_orders_are_reported_regardless_of_age(
    service: ShippingReminderService, repository: FakeOrderRepository
) -> None:
    await repository.save(_make_order("SENT", _TODAY_UTC, FULFILLMENT_SENT))
    await repository.save(_make_order("PROCESSING", _TODAY_UTC, FULFILLMENT_PROCESSING))
    await repository.save(_make_order("READY", _TODAY_UTC, FULFILLMENT_READY_FOR_SHIPMENT))
    await repository.save(_make_order("NEW-TODAY", _TODAY_UTC, FULFILLMENT_NEW))
    await repository.save(_make_order("NEW-OLD", _LAST_WEEK_UTC, FULFILLMENT_NEW))

    result = await service.build_reminder()

    assert result is not None
    assert result.new_count == 2
    new_ids = {o.external_id for o in result.new_orders}
    assert new_ids == {"NEW-TODAY", "NEW-OLD"}


async def test_cancelled_new_order_is_not_counted(
    service: ShippingReminderService, repository: FakeOrderRepository
) -> None:
    await repository.save(
        _make_order("CANCELLED", _TODAY_UTC, FULFILLMENT_NEW, status="CANCELLED")
    )
    await repository.save(_make_order("PENDING", _TODAY_UTC, FULFILLMENT_NEW))

    result = await service.build_reminder()

    assert result is not None
    assert result.new_count == 1
    assert result.new_orders[0].external_id == "PENDING"
