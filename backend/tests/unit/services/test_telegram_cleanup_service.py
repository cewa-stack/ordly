"""Testy jednostkowe TelegramCleanupService - nocne czyszczenie czatu (02:00)."""

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
    FULFILLMENT_SENT,
)
from app.services.telegram_cleanup_service import TelegramCleanupService
from tests.fakes.fake_bot import FakeBot
from tests.fakes.fake_notifier import FakeNotifier
from tests.fakes.fake_order_repository import FakeOrderRepository
from tests.fakes.fake_telegram_message_repository import (
    FakeTelegramMessageRepository,
)

_ADMIN_CHAT_ID = 123456789


def _make_order(
    external_id: str, fulfillment_status: str | None, status: str = "READY_FOR_PROCESSING"
) -> Order:
    return Order(
        external_id=external_id,
        marketplace="allegro",
        buyer=Customer(login="jan_kowalski"),
        products=[Product("PROD-1", "Olejek", 1, Decimal("29.99"))],
        total_amount=Decimal("29.99"),
        currency="PLN",
        status=status,
        order_date=datetime(2026, 7, 20, 10, 0, 0),
        fulfillment_status=fulfillment_status,
    )


@pytest.fixture
def bot() -> FakeBot:
    return FakeBot()


@pytest.fixture
def orders() -> FakeOrderRepository:
    return FakeOrderRepository()


@pytest.fixture
def messages() -> FakeTelegramMessageRepository:
    return FakeTelegramMessageRepository()


@pytest.fixture
def notifier() -> FakeNotifier:
    return FakeNotifier()


@pytest.fixture
def service(
    bot: FakeBot,
    orders: FakeOrderRepository,
    messages: FakeTelegramMessageRepository,
    notifier: FakeNotifier,
) -> TelegramCleanupService:
    return TelegramCleanupService(
        bot=bot,
        admin_chat_id=_ADMIN_CHAT_ID,
        order_repository=orders,
        message_repository=messages,
        notifier=notifier,
    )


async def test_purge_deletes_all_tracked_messages(
    service: TelegramCleanupService,
    bot: FakeBot,
    messages: FakeTelegramMessageRepository,
) -> None:
    await messages.record(_ADMIN_CHAT_ID, 10)
    await messages.record(_ADMIN_CHAT_ID, 11)

    deleted = await service.purge_previous_messages()

    assert deleted == 2
    assert bot.deleted == [(_ADMIN_CHAT_ID, 10), (_ADMIN_CHAT_ID, 11)]
    assert await messages.get_all() == []


async def test_purge_is_resilient_to_undeletable_message(
    service: TelegramCleanupService,
    bot: FakeBot,
    messages: FakeTelegramMessageRepository,
) -> None:
    await messages.record(_ADMIN_CHAT_ID, 10)
    await messages.record(_ADMIN_CHAT_ID, 11)
    bot.fail_message_ids = {10}

    deleted = await service.purge_previous_messages()

    assert deleted == 1
    assert bot.deleted == [(_ADMIN_CHAT_ID, 11)]
    assert await messages.get_all() == []


async def test_repost_publishes_only_active_orders(
    service: TelegramCleanupService,
    orders: FakeOrderRepository,
    notifier: FakeNotifier,
) -> None:
    await orders.save(_make_order("NEW-1", FULFILLMENT_NEW))
    await orders.save(_make_order("PACK-1", FULFILLMENT_PROCESSING))
    await orders.save(_make_order("SENT-1", FULFILLMENT_SENT))
    await orders.save(_make_order("CANC-1", FULFILLMENT_NEW, status="CANCELLED"))

    reposted = await service.repost_active_orders()

    assert reposted == 2
    assert len(notifier.sent_active_orders) == 1
    published_ids = {o.external_id for o in notifier.sent_active_orders[0]}
    assert published_ids == {"NEW-1", "PACK-1"}


async def test_repost_sends_nothing_when_no_active_orders(
    service: TelegramCleanupService,
    orders: FakeOrderRepository,
    notifier: FakeNotifier,
) -> None:
    await orders.save(_make_order("SENT-1", FULFILLMENT_SENT))

    reposted = await service.repost_active_orders()

    assert reposted == 0
    assert notifier.sent_active_orders == []
