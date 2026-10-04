"""
Synchronizacja zgłasza zwroty z oddanymi pieniędzmi (`ReturnRefunded`) -
źródło wpisów "zwrot pieniędzy" w rejestrze anulowań i zwrotów. Plus
odczyt powodu zwrotu z odpowiedzi Allegro.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.core.event_bus.bus import EventBus
from app.core.event_bus.events import ReturnRefunded
from app.domain.customer_cases import (
    REASON_BUYER_RESIGNED,
    REASON_OTHER,
    clean_login,
    reason_from_allegro_return,
)
from app.infrastructure.plugins.allegro.mapper import map_customer_return_to_domain
from app.services.sync_orders_service import SyncOrdersService


async def _sync(plugin, orders, returns) -> list[ReturnRefunded]:
    bus = EventBus()
    seen: list[ReturnRefunded] = []

    async def capture(event: ReturnRefunded) -> None:
        seen.append(event)

    bus.subscribe(ReturnRefunded, capture)
    service = SyncOrdersService(plugin, orders, bus, returns)
    result = await service.sync_new_orders()
    await service.publish_sync_events(result)
    return seen


class TestZwrotPieniedzy:
    @pytest.mark.asyncio
    async def test_przejscie_na_pieniadze_oddane(
        self, fake_marketplace_plugin, fake_order_repository, fake_return_repository, sample_return
    ):
        fake_marketplace_plugin.returns_to_return = [replace(sample_return, status="CREATED")]
        assert await _sync(
            fake_marketplace_plugin, fake_order_repository, fake_return_repository
        ) == []

        fake_marketplace_plugin.returns_to_return = [replace(sample_return, status="FINISHED")]
        events = await _sync(
            fake_marketplace_plugin, fake_order_repository, fake_return_repository
        )

        assert [e.order_return.status for e in events] == ["FINISHED"]

    @pytest.mark.asyncio
    async def test_nowy_zwrot_juz_rozliczony(
        self, fake_marketplace_plugin, fake_order_repository, fake_return_repository, sample_return
    ):
        fake_marketplace_plugin.returns_to_return = [replace(sample_return, status="FINISHED")]

        events = await _sync(
            fake_marketplace_plugin, fake_order_repository, fake_return_repository
        )

        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_kolejne_statusy_po_zwrocie_nie_dublują(
        self, fake_marketplace_plugin, fake_order_repository, fake_return_repository, sample_return
    ):
        fake_marketplace_plugin.returns_to_return = [replace(sample_return, status="FINISHED")]
        await _sync(fake_marketplace_plugin, fake_order_repository, fake_return_repository)

        fake_marketplace_plugin.returns_to_return = [
            replace(sample_return, status="COMMISSION_REFUNDED")
        ]
        events = await _sync(
            fake_marketplace_plugin, fake_order_repository, fake_return_repository
        )

        assert events == []


class TestPowodZAllegro:
    def test_mapper_czyta_kod_powodu_bez_komentarza(self):
        raw = {
            "id": "RET-1",
            "orderId": "ORD-1",
            "status": "FINISHED",
            "items": [
                {"offerId": "1", "name": "Kubek", "quantity": 1, "reason": {}},
                {
                    "offerId": "2",
                    "name": "Świeca",
                    "quantity": 1,
                    "reason": {"type": "DONT_LIKE_IT", "userComment": "tekst kupującego"},
                },
            ],
        }

        order_return = map_customer_return_to_domain(raw)

        assert order_return.reason_type == "DONT_LIKE_IT"

    def test_brak_powodu(self):
        assert map_customer_return_to_domain({"id": "RET-2"}).reason_type is None

    def test_mapowanie_powodow(self):
        assert reason_from_allegro_return("DONT_LIKE_IT") == REASON_BUYER_RESIGNED
        assert reason_from_allegro_return("DAMAGED") == REASON_OTHER
        assert reason_from_allegro_return(None) is None

    def test_zaslepka_loginu(self):
        assert clean_login("nieznany") is None
        assert clean_login("  ") is None
        assert clean_login("anna_k") == "anna_k"
