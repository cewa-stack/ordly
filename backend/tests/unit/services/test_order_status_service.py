"""
Ręczny status aplikacyjny w akcji: zapis, historia, synchronizacja
z Allegro i powiadomienia - pozycje z Notion "Brak ręcznej zmiany statusu
zamówienia wyłącznie w aplikacji", "Nieprawidłowa obsługa powiadomień po
ręcznej zmianie statusu" i "Brak jednoznacznych reguł priorytetu...".
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.core.event_bus.bus import EventBus
from app.core.event_bus.events import OrderCancelled, OrderPackingStarted
from app.domain.exceptions.domain_exceptions import OrderNotFoundError
from app.domain.order_status import effective_app_status, is_manual_in_force
from app.services.attention_service import is_pending_packing
from app.services.order_status_service import OrderStatusService
from app.services.shipping_reminder_service import ShippingReminderService
from app.services.sync_orders_service import SyncOrdersService

PAID = "READY_FOR_PROCESSING"


@pytest.fixture
def new_order(sample_order):
    return replace(sample_order, status=PAID, fulfillment_status="NEW")


async def _sync(plugin, repository, returned):
    """Jeden cykl synchronizacji; zwraca zdarzenia, które wyszły."""
    plugin.orders_to_return = returned
    bus = EventBus()
    seen: list[object] = []

    async def capture(event) -> None:
        seen.append(event)

    bus.subscribe(OrderCancelled, capture)
    bus.subscribe(OrderPackingStarted, capture)
    service = SyncOrdersService(plugin, repository, bus)
    result = await service.sync_new_orders()
    await service.publish_sync_events(result)
    return seen


class TestRecznaZmiana:
    @pytest.mark.asyncio
    async def test_zapis_i_historia(self, fake_order_repository, new_order):
        await fake_order_repository.save(new_order)
        service = OrderStatusService(fake_order_repository)

        updated = await service.set_app_status(new_order.external_id, "IN_PROGRESS")

        assert effective_app_status(updated) == "IN_PROGRESS"
        assert is_manual_in_force(updated)
        assert updated.app_status_changed_at is not None
        # Po "odświeżeniu" (ponowny odczyt z repozytorium) status zostaje.
        reread = await fake_order_repository.get_by_external_id(new_order.external_id)
        assert reread is not None and effective_app_status(reread) == "IN_PROGRESS"
        history = await service.history(new_order.external_id)
        assert [(h.previous_status, h.new_status, h.source) for h in history] == [
            ("NEW", "IN_PROGRESS", "manual")
        ]

    @pytest.mark.asyncio
    async def test_przywrocenie_statusu_z_allegro(self, fake_order_repository, new_order):
        await fake_order_repository.save(new_order)
        service = OrderStatusService(fake_order_repository)
        await service.set_app_status(new_order.external_id, "DONE")

        restored = await service.set_app_status(new_order.external_id, None)

        assert restored.app_status is None
        assert effective_app_status(restored) == "NEW"
        history = await service.history(new_order.external_id)
        assert history[0].source == "restore_allegro"

    @pytest.mark.asyncio
    async def test_nieznane_zamowienie(self, fake_order_repository):
        with pytest.raises(OrderNotFoundError):
            await OrderStatusService(fake_order_repository).set_app_status("BRAK", "DONE")

    @pytest.mark.asyncio
    async def test_zmiana_nie_wola_allegro(
        self, fake_order_repository, fake_marketplace_plugin, new_order
    ):
        await fake_order_repository.save(new_order)
        await OrderStatusService(fake_order_repository).set_app_status(
            new_order.external_id, "DONE"
        )
        assert fake_marketplace_plugin.fulfillment_calls == []


class TestSynchronizacja:
    @pytest.mark.asyncio
    async def test_sync_nie_nadpisuje_recznego_statusu(
        self, fake_order_repository, fake_marketplace_plugin, new_order
    ):
        await fake_order_repository.save(replace(new_order, fulfillment_status="PROCESSING"))
        await OrderStatusService(fake_order_repository).set_app_status(
            new_order.external_id, "NEW"
        )

        # Allegro kilka razy zwraca ten sam etap.
        for _ in range(3):
            await _sync(
                fake_marketplace_plugin,
                fake_order_repository,
                [replace(new_order, fulfillment_status="PROCESSING")],
            )

        stored = await fake_order_repository.get_by_external_id(new_order.external_id)
        assert stored is not None
        assert stored.app_status == "NEW"
        assert effective_app_status(stored) == "NEW"

    @pytest.mark.asyncio
    async def test_anulowanie_z_allegro_po_zamknieciu_bez_powiadomienia(
        self, fake_order_repository, fake_marketplace_plugin, new_order
    ):
        await fake_order_repository.save(new_order)
        await OrderStatusService(fake_order_repository).set_app_status(
            new_order.external_id, "CANCELLED"
        )

        events = await _sync(
            fake_marketplace_plugin,
            fake_order_repository,
            [replace(new_order, status="CANCELLED")],
        )

        cancelled = [e for e in events if isinstance(e, OrderCancelled)]
        assert len(cancelled) == 1 and cancelled[0].notify is False

    @pytest.mark.asyncio
    async def test_anulowanie_bez_recznego_statusu_z_powiadomieniem(
        self, fake_order_repository, fake_marketplace_plugin, new_order
    ):
        await fake_order_repository.save(new_order)
        events = await _sync(
            fake_marketplace_plugin,
            fake_order_repository,
            [replace(new_order, status="CANCELLED")],
        )
        cancelled = [e for e in events if isinstance(e, OrderCancelled)]
        assert len(cancelled) == 1 and cancelled[0].notify is True

    @pytest.mark.asyncio
    async def test_d2a_zrealizowane_anulowane_przez_allegro(
        self, fake_order_repository, fake_marketplace_plugin, new_order
    ):
        await fake_order_repository.save(new_order)
        await OrderStatusService(fake_order_repository).set_app_status(
            new_order.external_id, "DONE"
        )

        events = await _sync(
            fake_marketplace_plugin,
            fake_order_repository,
            [replace(new_order, status="CANCELLED")],
        )

        stored = await fake_order_repository.get_by_external_id(new_order.external_id)
        assert stored is not None and effective_app_status(stored) == "CANCELLED"
        assert [e.notify for e in events if isinstance(e, OrderCancelled)] == [False]

    @pytest.mark.asyncio
    async def test_brak_sms_o_pakowaniu_po_zamknieciu(
        self, fake_order_repository, fake_marketplace_plugin, new_order
    ):
        await fake_order_repository.save(new_order)
        await OrderStatusService(fake_order_repository).set_app_status(
            new_order.external_id, "DONE"
        )

        events = await _sync(
            fake_marketplace_plugin,
            fake_order_repository,
            [replace(new_order, fulfillment_status="PROCESSING")],
        )

        assert not [e for e in events if isinstance(e, OrderPackingStarted)]

    @pytest.mark.asyncio
    async def test_sms_o_pakowaniu_dla_w_realizacji_jak_dotad(
        self, fake_order_repository, fake_marketplace_plugin, new_order
    ):
        """Ręczne "W realizacji" nie blokuje automatyzacji etapu PROCESSING."""
        await fake_order_repository.save(new_order)
        await OrderStatusService(fake_order_repository).set_app_status(
            new_order.external_id, "IN_PROGRESS"
        )
        events = await _sync(
            fake_marketplace_plugin,
            fake_order_repository,
            [replace(new_order, fulfillment_status="PROCESSING")],
        )
        assert len([e for e in events if isinstance(e, OrderPackingStarted)]) == 1


class TestPrzypomnieniaIPlakietka:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("closed", ["DONE", "CANCELLED"])
    async def test_zamkniete_znikaja_z_przypomnien(
        self, fake_order_repository, new_order, closed
    ):
        await fake_order_repository.save(new_order)
        await OrderStatusService(fake_order_repository).set_app_status(
            new_order.external_id, closed
        )

        assert await ShippingReminderService(fake_order_repository).build_reminder() is None
        assert await fake_order_repository.get_active(50) == []
        stored = await fake_order_repository.get_by_external_id(new_order.external_id)
        assert stored is not None and not is_pending_packing(stored)

    @pytest.mark.asyncio
    async def test_reczne_nowe_wraca_do_przypomnienia(self, fake_order_repository, new_order):
        await fake_order_repository.save(replace(new_order, fulfillment_status="PROCESSING"))
        assert await ShippingReminderService(fake_order_repository).build_reminder() is None

        await OrderStatusService(fake_order_repository).set_app_status(
            new_order.external_id, "NEW"
        )

        reminder = await ShippingReminderService(fake_order_repository).build_reminder()
        assert reminder is not None and len(reminder.new_orders) == 1
