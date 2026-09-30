"""
SqliteOrderRepository.get_open_for_refresh na prawdziwej bazie SQLite -
kandydaci do potwierdzenia u źródła (zamówienia spoza okna synchronizacji).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from app.domain.entities.shipment import Shipment
from app.repositories.sqlite_order_repository import SqliteOrderRepository
from app.repositories.sqlite_shipment_repository import SqliteShipmentRepository

_ORDER_DATE = datetime(2026, 7, 20, 10, 0, 0)


class TestGetOpenForRefresh:
    @pytest.mark.asyncio
    async def test_zwraca_tylko_otwarte_bez_numeru_z_danego_marketplace(
        self, in_memory_session, sample_order
    ):
        repository = SqliteOrderRepository(in_memory_session)
        shipments = SqliteShipmentRepository(in_memory_session)

        def make(external_id: str, fulfillment: str | None, **changes: object):
            fields: dict[str, object] = {
                "external_id": external_id,
                "fulfillment_status": fulfillment,
                "order_date": _ORDER_DATE,
                **changes,
            }
            return replace(sample_order, **fields)  # type: ignore[arg-type]

        orders = [
            make("NEW", "NEW", order_date=datetime(2026, 7, 21)),
            make("NULL", None),
            make("PROC", "PROCESSING", order_date=datetime(2026, 7, 19)),
            make("READY", "READY_FOR_SHIPMENT", order_date=datetime(2026, 7, 18)),
            make("SENT", "SENT"),
            make("PICKED", "PICKED_UP"),
            make("RETURNED", "RETURNED"),
            make("CANC", "NEW", status="CANCELLED"),
            make("TRACK", "NEW"),
            make("LOKALNIE", "NEW", marketplace="allegro_lokalnie"),
        ]
        for order in orders:
            await repository.save(order)
        await in_memory_session.commit()
        await shipments.save_check_result(
            "TRACK",
            Shipment(
                order_external_id="TRACK",
                carrier="INPOST",
                tracking_number="6200000000",
                status="NADANA",
                updated_at=None,
            ),
        )
        await in_memory_session.commit()

        found = await repository.get_open_for_refresh("allegro", limit=50)

        assert [o.external_id for o in found] == ["NEW", "NULL", "PROC", "READY"]
        assert len(await repository.get_open_for_refresh("allegro", limit=2)) == 2
