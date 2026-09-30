"""
Jedna reguła "wymaga działania" dla aplikacji, bota i powiadomień -
pozycja z Notion "Kompleksowy przegląd i uporządkowanie systemu
powiadomień dotyczących zamówień".

Reguła żyje w app/domain/fulfillment.py (`requires_packing`,
`awaits_shipment`). SqliteOrderRepository ma jej lustro w SQL, a API
wystawia jej wynik w `requires_packing`. Ten test sprawdza na prawdziwej
bazie, że dla KAŻDEJ kombinacji statusu płatności, etapu realizacji
i numeru przesyłki wszystkie miejsca mówią to samo.
"""

from __future__ import annotations

import itertools
from dataclasses import replace
from datetime import datetime

import pytest

from app.api.schemas import order_out
from app.domain.entities.order import Order
from app.domain.entities.shipment import Shipment
from app.domain.fulfillment import awaits_shipment, requires_packing
from app.repositories.sqlite_order_repository import SqliteOrderRepository
from app.repositories.sqlite_shipment_repository import SqliteShipmentRepository
from app.services.attention_service import is_pending_packing
from app.services.shipping_reminder_service import ShippingReminderService

_STATUSES = ("READY_FOR_PROCESSING", "CANCELLED")
_FULFILLMENTS = (
    None,
    "NEW",
    "PROCESSING",
    "READY_FOR_SHIPMENT",
    "READY_FOR_PICKUP",
    "SENT",
    "PICKED_UP",
    "SUSPENDED",
    "CANCELLED",
    "RETURNED",
)
_TRACKING = (None, "620000123")


async def _seed(session, sample_order: Order) -> list[Order]:
    repository = SqliteOrderRepository(session)
    shipments = SqliteShipmentRepository(session)
    seeded: list[Order] = []
    for index, (status, fulfillment, tracking) in enumerate(
        itertools.product(_STATUSES, _FULFILLMENTS, _TRACKING)
    ):
        order = replace(
            sample_order,
            external_id=f"O-{index:03d}",
            status=status,
            fulfillment_status=fulfillment,
            order_date=datetime(2026, 9, 1, 0, 0, index % 60),
            tracking_number=tracking,
        )
        await repository.save(order)
        seeded.append(order)
    await session.commit()
    for order in seeded:
        if order.tracking_number:
            await shipments.save_check_result(
                order.external_id,
                Shipment(
                    order_external_id=order.external_id,
                    carrier="INPOST",
                    tracking_number=order.tracking_number,
                    status="NADANA",
                    updated_at=None,
                ),
            )
    await session.commit()
    return seeded


def _ids(orders) -> set[str]:
    return {order.external_id for order in orders}


class TestJednaRegula:
    @pytest.mark.asyncio
    async def test_sql_bot_api_i_plakietka_licza_tak_samo(self, in_memory_session, sample_order):
        seeded = await _seed(in_memory_session, sample_order)
        repository = SqliteOrderRepository(in_memory_session)

        expected_packing = {
            o.external_id
            for o in seeded
            if requires_packing(o.status, o.fulfillment_status, o.tracking_number)
        }
        expected_shipment = {
            o.external_id
            for o in seeded
            if awaits_shipment(o.status, o.fulfillment_status, o.tracking_number)
        }

        stored = await repository.get_recent(limit=500)
        # Aplikacje (flaga z API) i plakietka/raport (AttentionService).
        assert {o.external_id for o in stored if order_out(o).requires_packing} == (
            expected_packing
        )
        assert {o.external_id for o in stored if is_pending_packing(o)} == expected_packing
        # Bot: czat po czyszczeniu 02:00.
        assert _ids(await repository.get_active(500)) == expected_packing
        # Bot: przypomnienie 20:00 = podzbiór "nietknięte" (NEW).
        untouched = {
            o.external_id for o in seeded if o.external_id in expected_packing
            and o.fulfillment_status == "NEW"
        }
        assert _ids(await repository.get_new_status()) == untouched
        reminder = await ShippingReminderService(repository).build_reminder()
        assert reminder is not None and _ids(reminder.new_orders) == untouched
        # Kafel "Do wysyłki" i kandydaci check_waybills_job.
        assert _ids(await repository.get_unshipped_since(datetime(2000, 1, 1))) == (
            expected_shipment
        )

    def test_regula_w_punktach(self):
        # Czeka na spakowanie tylko NEW/PROCESSING bez numeru, nieanulowane.
        assert requires_packing("READY_FOR_PROCESSING", "NEW", None)
        assert requires_packing("READY_FOR_PROCESSING", "processing", None)
        assert not requires_packing("READY_FOR_PROCESSING", None, None)
        assert not requires_packing("READY_FOR_PROCESSING", "NEW", "620000123")
        assert not requires_packing("CANCELLED", "NEW", None)
        assert not requires_packing("READY_FOR_PROCESSING", "CANCELLED", None)
        assert not requires_packing("READY_FOR_PROCESSING", "READY_FOR_SHIPMENT", None)
        assert not requires_packing("READY_FOR_PROCESSING", "RETURNED", None)
        # Do wysyłki dodatkowo spakowane; zwrócone/wstrzymane/do odbioru - nie.
        assert awaits_shipment("READY_FOR_PROCESSING", "READY_FOR_SHIPMENT", None)
        assert not awaits_shipment("READY_FOR_PROCESSING", "RETURNED", None)
        assert not awaits_shipment("READY_FOR_PROCESSING", "SUSPENDED", None)
        assert not awaits_shipment("READY_FOR_PROCESSING", "READY_FOR_PICKUP", None)
        assert not awaits_shipment("READY_FOR_PROCESSING", None, None)
