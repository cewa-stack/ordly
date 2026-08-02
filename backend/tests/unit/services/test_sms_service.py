"""Testy jednostkowe SmsService - SMS o rozpoczęciu pakowania."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from app.domain.entities.customer import Customer
from app.domain.entities.order import Order
from app.domain.entities.product import Product
from app.domain.entities.sms_message import (
    MESSAGE_TYPE_PACKING_STARTED,
    SMS_STATUS_FAILED,
    SMS_STATUS_SENT,
    SMS_STATUS_SKIPPED_NO_PHONE,
)
from app.services.sms_service import PACKING_STARTED_TEXT, SmsService
from tests.fakes.fake_sms_history_repository import FakeSmsHistoryRepository
from tests.fakes.fake_sms_provider import FakeSmsProvider


def _make_order(phone: str | None, external_id: str = "ORDER-001") -> Order:
    return Order(
        external_id=external_id,
        marketplace="allegro",
        buyer=Customer(login="jan_kowalski", email=None, phone_number=phone),
        products=[Product("PROD-1", "Olejek", 1, Decimal("29.99"))],
        total_amount=Decimal("29.99"),
        currency="PLN",
        status="READY_FOR_PROCESSING",
        order_date=datetime(2026, 7, 20, 10, 0, 0),
    )


@pytest.fixture
def provider() -> FakeSmsProvider:
    return FakeSmsProvider()


@pytest.fixture
def history() -> FakeSmsHistoryRepository:
    return FakeSmsHistoryRepository()


@pytest.fixture
def service(provider: FakeSmsProvider, history: FakeSmsHistoryRepository) -> SmsService:
    return SmsService(provider, history)


async def test_sends_sms_with_correct_text(
    service: SmsService, provider: FakeSmsProvider, history: FakeSmsHistoryRepository
) -> None:
    order = _make_order(phone="+48555111222")

    outcome = await service.send_packing_started(order)

    assert outcome.sent is True
    assert provider.sent == [("+48555111222", PACKING_STARTED_TEXT)]
    assert len(history.records) == 1
    assert history.records[0].status == SMS_STATUS_SENT
    assert history.records[0].message_type == MESSAGE_TYPE_PACKING_STARTED


async def test_skips_when_no_phone(
    service: SmsService, provider: FakeSmsProvider, history: FakeSmsHistoryRepository
) -> None:
    order = _make_order(phone=None)

    outcome = await service.send_packing_started(order)

    assert outcome.sent is False
    assert outcome.skipped_reason == "no_phone"
    assert provider.sent == []
    assert history.records[0].status == SMS_STATUS_SKIPPED_NO_PHONE


async def test_does_not_send_twice(service: SmsService, provider: FakeSmsProvider) -> None:
    order = _make_order(phone="+48555111222")

    first = await service.send_packing_started(order)
    second = await service.send_packing_started(order)

    assert first.sent is True
    assert second.sent is False
    assert second.skipped_reason == "already_sent"
    assert len(provider.sent) == 1


async def test_provider_exception_does_not_propagate(
    service: SmsService, provider: FakeSmsProvider, history: FakeSmsHistoryRepository
) -> None:
    provider.should_raise = True
    order = _make_order(phone="+48555111222")

    outcome = await service.send_packing_started(order)

    assert outcome.sent is False
    assert outcome.skipped_reason == "provider_error"
    assert history.records[0].status == SMS_STATUS_FAILED


async def test_provider_rejection_is_recorded_as_failed(
    service: SmsService, provider: FakeSmsProvider, history: FakeSmsHistoryRepository
) -> None:
    provider.should_fail = True
    order = _make_order(phone="+48555111222")

    outcome = await service.send_packing_started(order)

    assert outcome.sent is False
    assert outcome.skipped_reason == "provider_failed"
    assert history.records[0].status == SMS_STATUS_FAILED


async def test_retry_allowed_after_failure(
    service: SmsService, provider: FakeSmsProvider
) -> None:
    """Nieudana próba nie blokuje kolejnej - dopiero sukces zamyka wysyłkę."""
    order = _make_order(phone="+48555111222")
    provider.should_fail = True
    await service.send_packing_started(order)

    provider.should_fail = False
    outcome = await service.send_packing_started(order)

    assert outcome.sent is True
    assert len(provider.sent) == 1
