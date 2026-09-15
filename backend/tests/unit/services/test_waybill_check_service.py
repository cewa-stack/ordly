"""Testy jednostkowe WaybillCheckService."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.domain.fulfillment import FULFILLMENT_READY_FOR_SHIPMENT
from app.services.waybill_check_service import WaybillCheckService
from app.utils.time import utc_now


class TestWaybillCheckService:
    """Testy automatycznego wykrywania numerów przesyłek."""

    @pytest.mark.asyncio
    async def test_zapisuje_numer_przesylki_bez_zmiany_fulfillment_status(
        self, fake_marketplace_plugin, fake_order_repository, fake_shipment_repository, sample_order
    ):
        """Wykrycie przesyłki nie może dotknąć fulfillment_status - patrz plan."""
        order = replace(
            sample_order,
            order_date=utc_now(),
            fulfillment_status=FULFILLMENT_READY_FOR_SHIPMENT,
        )
        await fake_order_repository.save(order)
        service = WaybillCheckService(
            fake_marketplace_plugin, fake_order_repository, fake_shipment_repository
        )

        detected = await service.check_new_waybills()

        assert detected == 1
        stored = await fake_order_repository.get_by_external_id(order.external_id)
        assert stored.fulfillment_status == FULFILLMENT_READY_FOR_SHIPMENT
        saved = await fake_shipment_repository.get_last_known(order.external_id)
        assert saved.tracking_number == "TEST123456"

    @pytest.mark.asyncio
    async def test_pomija_zamowienia_bez_jeszcze_nadanej_przesylki(
        self, fake_marketplace_plugin, fake_order_repository, fake_shipment_repository, sample_order
    ):
        """Większość cykli nie znajdzie nic nowego - to normalny, oczekiwany przypadek."""
        order = replace(sample_order, order_date=utc_now())
        await fake_order_repository.save(order)
        fake_marketplace_plugin.orders_without_waybill.add(order.external_id)
        service = WaybillCheckService(
            fake_marketplace_plugin, fake_order_repository, fake_shipment_repository
        )

        detected = await service.check_new_waybills()

        assert detected == 0

    @pytest.mark.asyncio
    async def test_przerywa_cykl_gdy_allegro_niedostepne(
        self, fake_marketplace_plugin, fake_order_repository, fake_shipment_repository, sample_order
    ):
        """Niedostępność Allegro nie może wywrócić joba - próba wraca następnym razem."""
        order = replace(sample_order, order_date=utc_now())
        await fake_order_repository.save(order)
        fake_marketplace_plugin.should_raise_tracking_api_error = True
        service = WaybillCheckService(
            fake_marketplace_plugin, fake_order_repository, fake_shipment_repository
        )

        detected = await service.check_new_waybills()

        assert detected == 0
