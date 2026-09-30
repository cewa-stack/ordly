"""
Pozycja z Notion "Brak prawidłowej synchronizacji statusu zamówienia
i numeru przesyłki z Allegro" - na prawdziwej bazie SQLite.

Numer przesyłki przypisany automatycznie (etykieta, integracja
przewoźnika) nie zmienia etapu realizacji na Allegro, jeśli sprzedawca
nie włączył automatycznej zmiany statusu. Synchronizacja co minutę widzi
go jednak w checkout-formie: `fulfillment.shipmentSummary.lineItemsSent`
= SOME/ALL. Dotąd ORDLY to ignorowało i czekało na osobny job co 5 minut,
a bot (przypomnienie 20:00, czat po czyszczeniu 02:00) nie patrzył na
numer przesyłki w ogóle.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from app.core.event_bus.bus import EventBus
from app.domain.entities.order import Order
from app.domain.entities.shipment import Shipment
from app.repositories.sqlite_order_repository import SqliteOrderRepository
from app.repositories.sqlite_return_repository import SqliteReturnRepository
from app.repositories.sqlite_shipment_repository import SqliteShipmentRepository
from app.services.attention_service import AttentionService
from app.services.issues_service import IssuesService
from app.services.shipping_reminder_service import ShippingReminderService
from app.services.sync_orders_service import SyncOrdersService
from app.services.tracking_service import TrackingService

_SINCE_EPOCH = datetime(2000, 1, 1)


def _new(sample_order: Order) -> Order:
    return replace(sample_order, status="READY_FOR_PROCESSING", fulfillment_status="NEW")


def _service(plugin, session) -> SyncOrdersService:
    return SyncOrdersService(
        plugin,
        SqliteOrderRepository(session),
        EventBus(),
        SqliteReturnRepository(session),
        shipment_repository=SqliteShipmentRepository(session),
    )


async def _sync(plugin, session) -> None:
    service = _service(plugin, session)
    result = await service.sync_new_orders()
    await session.commit()
    await service.publish_sync_events(result)
    # Na produkcji każdy cykl ma własną sesję - tu jedna sesja udaje
    # kolejne cykle, więc czyścimy mapę tożsamości jak po zamknięciu sesji.
    session.expire_all()


class TestNumerPrzesylkiWSynchronizacji:
    @pytest.mark.asyncio
    async def test_numer_zgloszony_w_checkout_formie_zdejmuje_zamowienie_z_nowych(
        self, in_memory_session, fake_marketplace_plugin, sample_order
    ):
        repository = SqliteOrderRepository(in_memory_session)
        order = _new(sample_order)
        await repository.save(order)
        await in_memory_session.commit()
        # Allegro: etap nadal NEW, ale pozycje mają już numer przesyłki.
        fake_marketplace_plugin.orders_to_return = [replace(order, line_items_sent="ALL")]

        await _sync(fake_marketplace_plugin, in_memory_session)

        stored = await repository.get_by_external_id(order.external_id)
        assert stored is not None
        assert stored.tracking_number == "TEST123456"
        assert await repository.get_new_status() == []  # bot: przypomnienie 20:00
        assert await repository.get_active(50) == []  # bot: czat po 02:00
        assert await repository.get_unshipped_since(_SINCE_EPOCH) == []  # kafel "do wysłania"
        assert await ShippingReminderService(repository).build_reminder() is None
        attention = AttentionService(
            repository,
            SqliteReturnRepository(in_memory_session),
            IssuesService(fake_marketplace_plugin),
        )
        assert (await attention.counts()).pending == 0  # licznik i plakietka

    @pytest.mark.asyncio
    async def test_kolejna_synchronizacja_nie_odpytuje_ponownie_i_nie_przywraca_nowego(
        self, in_memory_session, fake_marketplace_plugin, sample_order
    ):
        repository = SqliteOrderRepository(in_memory_session)
        order = _new(sample_order)
        await repository.save(order)
        await in_memory_session.commit()
        fake_marketplace_plugin.orders_to_return = [replace(order, line_items_sent="SOME")]

        await _sync(fake_marketplace_plugin, in_memory_session)
        await _sync(fake_marketplace_plugin, in_memory_session)
        # Restart usługi = nowy serwis na tej samej bazie.
        await _sync(fake_marketplace_plugin, in_memory_session)

        assert fake_marketplace_plugin.tracking_calls == [order.external_id]
        assert await repository.get_new_status() == []

    @pytest.mark.asyncio
    async def test_bez_zgloszonego_numeru_nie_ma_dodatkowych_zapytan(
        self, in_memory_session, fake_marketplace_plugin, sample_order
    ):
        repository = SqliteOrderRepository(in_memory_session)
        order = _new(sample_order)
        await repository.save(order)
        await in_memory_session.commit()
        fake_marketplace_plugin.orders_to_return = [replace(order, line_items_sent="NONE")]

        await _sync(fake_marketplace_plugin, in_memory_session)

        assert fake_marketplace_plugin.tracking_calls == []
        # Zamówienie naprawdę czekające na spakowanie nadal jest widoczne.
        assert [o.external_id for o in await repository.get_new_status()] == [
            order.external_id
        ]

    @pytest.mark.asyncio
    async def test_nowe_zamowienie_z_numerem_od_razu(
        self, in_memory_session, fake_marketplace_plugin, sample_order
    ):
        repository = SqliteOrderRepository(in_memory_session)
        fake_marketplace_plugin.orders_to_return = [
            replace(_new(sample_order), line_items_sent="ALL")
        ]

        await _sync(fake_marketplace_plugin, in_memory_session)

        stored = await repository.get_by_external_id(sample_order.external_id)
        assert stored is not None and stored.tracking_number == "TEST123456"

    @pytest.mark.asyncio
    async def test_blad_pobrania_przesylek_nie_przerywa_synchronizacji(
        self, in_memory_session, fake_marketplace_plugin, sample_order
    ):
        repository = SqliteOrderRepository(in_memory_session)
        order = _new(sample_order)
        await repository.save(order)
        await in_memory_session.commit()
        fake_marketplace_plugin.should_raise_tracking_api_error = True
        fake_marketplace_plugin.orders_to_return = [
            replace(order, line_items_sent="ALL", fulfillment_status="PROCESSING")
        ]

        await _sync(fake_marketplace_plugin, in_memory_session)

        stored = await repository.get_by_external_id(order.external_id)
        assert stored is not None
        assert stored.fulfillment_status == "PROCESSING"  # status zapisany mimo błędu
        assert stored.tracking_number is None

    @pytest.mark.asyncio
    async def test_niepelna_odpowiedz_nie_nadpisuje_statusow(
        self, in_memory_session, fake_marketplace_plugin, sample_order
    ):
        repository = SqliteOrderRepository(in_memory_session)
        order = replace(_new(sample_order), fulfillment_status="SENT")
        await repository.save(order)
        await in_memory_session.commit()
        # Ucięta odpowiedź: brak `fulfillment` i brak `status`.
        fake_marketplace_plugin.orders_to_return = [
            replace(order, fulfillment_status=None, status="UNKNOWN")
        ]

        await _sync(fake_marketplace_plugin, in_memory_session)

        stored = await repository.get_by_external_id(order.external_id)
        assert stored is not None
        assert stored.fulfillment_status == "SENT"
        assert stored.status == "READY_FOR_PROCESSING"

    @pytest.mark.asyncio
    async def test_status_zmieniony_na_allegro_jest_pobierany(
        self, in_memory_session, fake_marketplace_plugin, sample_order
    ):
        repository = SqliteOrderRepository(in_memory_session)
        order = _new(sample_order)
        await repository.save(order)
        await in_memory_session.commit()
        fake_marketplace_plugin.orders_to_return = [
            replace(order, fulfillment_status="READY_FOR_SHIPMENT")
        ]

        await _sync(fake_marketplace_plugin, in_memory_session)

        stored = await repository.get_by_external_id(order.external_id)
        assert stored is not None and stored.fulfillment_status == "READY_FOR_SHIPMENT"
        assert await repository.get_new_status() == []


class TestTrackingNieNadpisujeZnanegoNumeru:
    @pytest.mark.asyncio
    async def test_pusta_odpowiedz_allegro_nie_kasuje_zapisanego_numeru(
        self, in_memory_session, fake_marketplace_plugin, sample_order
    ):
        repository = SqliteOrderRepository(in_memory_session)
        shipments = SqliteShipmentRepository(in_memory_session)
        await repository.save(_new(sample_order))
        await in_memory_session.commit()
        await shipments.save_check_result(
            sample_order.external_id,
            Shipment(
                order_external_id=sample_order.external_id,
                carrier="INPOST",
                tracking_number="620000111",
                status="NADANA",
                updated_at=None,
            ),
        )
        await in_memory_session.commit()
        # Chwilowo pusta lista przesyłek z Allegro.
        fake_marketplace_plugin.orders_without_waybill.add(sample_order.external_id)

        shipment = await TrackingService(
            fake_marketplace_plugin, repository, shipments
        ).get_current_tracking(sample_order.external_id)
        await in_memory_session.commit()

        assert shipment.tracking_number == "620000111"
        stored = await repository.get_by_external_id(sample_order.external_id)
        assert stored is not None and stored.tracking_number == "620000111"
