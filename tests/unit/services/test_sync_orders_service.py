"""Testy jednostkowe SyncOrdersService - centralnej logiki biznesowej projektu."""

from __future__ import annotations

import pytest

from app.core.event_bus.bus import EventBus
from app.core.event_bus.events import (
    OrderCancelled,
    OrderCreated,
    OrderPackingStarted,
    OrderReturnCreated,
)
from app.domain.exceptions.domain_exceptions import MarketplaceUnavailableError
from app.services.sync_orders_service import SyncOrdersService


class TestSyncOrdersService:
    """Testy synchronizacji zamówień: nowe zamówienia, duplikaty, błędy API."""

    @pytest.mark.asyncio
    async def test_zapisuje_nowe_zamowienie_i_emituje_zdarzenie(
        self, fake_marketplace_plugin, fake_order_repository, sample_order
    ):
        """Nowe zamówienie powinno zostać zapisane i wyemitować OrderCreated."""
        fake_marketplace_plugin.orders_to_return = [sample_order]
        event_bus = EventBus()
        received_events: list[OrderCreated] = []

        async def capture(event: OrderCreated) -> None:
            received_events.append(event)

        event_bus.subscribe(OrderCreated, capture)

        service = SyncOrdersService(fake_marketplace_plugin, fake_order_repository, event_bus)
        result = await service.sync_new_orders()
        await service.publish_sync_events(result)

        assert result.new_orders_count == 1
        assert result.checked_orders_count == 1
        assert result.new_orders == (sample_order,)
        assert await fake_order_repository.exists("allegro", sample_order.external_id)
        assert len(received_events) == 1
        assert received_events[0].order.external_id == sample_order.external_id

    @pytest.mark.asyncio
    async def test_nie_zapisuje_ponownie_juz_istniejacego_zamowienia(
        self, fake_marketplace_plugin, fake_order_repository, sample_order
    ):
        """Zamówienie już zapisane wcześniej nie powinno zostać zdublowane."""
        await fake_order_repository.save(sample_order)
        fake_marketplace_plugin.orders_to_return = [sample_order]
        event_bus = EventBus()

        service = SyncOrdersService(fake_marketplace_plugin, fake_order_repository, event_bus)
        result = await service.sync_new_orders()

        assert result.new_orders_count == 0
        assert result.checked_orders_count == 1

    @pytest.mark.asyncio
    async def test_przy_niedostepnosci_api_rzuca_marketplace_unavailable(
        self, fake_marketplace_plugin, fake_order_repository
    ):
        """Błąd Allegro API powinien zostać przetłumaczony na wyjątek domenowy."""
        fake_marketplace_plugin.should_raise_api_error = True
        event_bus = EventBus()

        service = SyncOrdersService(fake_marketplace_plugin, fake_order_repository, event_bus)

        with pytest.raises(MarketplaceUnavailableError):
            await service.sync_new_orders()

    @pytest.mark.asyncio
    async def test_wiele_zamowien_liczone_poprawnie(
        self, fake_marketplace_plugin, fake_order_repository, sample_order
    ):
        """Sprawdza poprawne zliczanie przy mieszance nowych i istniejących zamówień."""
        from dataclasses import replace

        second_order = replace(sample_order, external_id="ORDER-002")
        await fake_order_repository.save(sample_order)
        fake_marketplace_plugin.orders_to_return = [sample_order, second_order]
        event_bus = EventBus()

        service = SyncOrdersService(fake_marketplace_plugin, fake_order_repository, event_bus)
        result = await service.sync_new_orders()

        assert result.new_orders_count == 1
        assert result.checked_orders_count == 2


class TestSyncOrderCancellation:
    """Testy wykrywania anulowania znanych zamówień podczas synchronizacji."""

    @pytest.mark.asyncio
    async def test_anulowanie_zamowienia_emituje_order_cancelled(
        self, fake_marketplace_plugin, fake_order_repository, sample_order
    ):
        """Zmiana statusu na CANCELLED powinna wyemitować OrderCancelled."""
        from dataclasses import replace

        await fake_order_repository.save(sample_order)
        cancelled_order = replace(sample_order, status="CANCELLED")
        fake_marketplace_plugin.orders_to_return = [cancelled_order]
        event_bus = EventBus()
        received_events: list[OrderCancelled] = []

        async def capture(event: OrderCancelled) -> None:
            received_events.append(event)

        event_bus.subscribe(OrderCancelled, capture)

        service = SyncOrdersService(fake_marketplace_plugin, fake_order_repository, event_bus)
        result = await service.sync_new_orders()
        await service.publish_sync_events(result)

        assert result.cancelled_orders == (cancelled_order,)
        assert len(received_events) == 1
        assert received_events[0].order.external_id == sample_order.external_id
        stored = await fake_order_repository.get_by_external_id(sample_order.external_id)
        assert stored is not None and stored.status == "CANCELLED"

    @pytest.mark.asyncio
    async def test_zwykla_zmiana_statusu_nie_emituje_order_cancelled(
        self, fake_marketplace_plugin, fake_order_repository, sample_order
    ):
        """Zmiana statusu inna niż anulowanie aktualizuje bazę bez zdarzenia."""
        from dataclasses import replace

        await fake_order_repository.save(sample_order)
        updated_order = replace(sample_order, status="SENT")
        fake_marketplace_plugin.orders_to_return = [updated_order]
        event_bus = EventBus()

        service = SyncOrdersService(fake_marketplace_plugin, fake_order_repository, event_bus)
        result = await service.sync_new_orders()

        assert result.cancelled_orders == ()
        stored = await fake_order_repository.get_by_external_id(sample_order.external_id)
        assert stored is not None and stored.status == "SENT"

    @pytest.mark.asyncio
    async def test_juz_anulowane_zamowienie_nie_jest_zglaszane_ponownie(
        self, fake_marketplace_plugin, fake_order_repository, sample_order
    ):
        """Zamówienie już anulowane w bazie nie generuje kolejnego powiadomienia."""
        from dataclasses import replace

        cancelled_order = replace(sample_order, status="CANCELLED")
        await fake_order_repository.save(cancelled_order)
        fake_marketplace_plugin.orders_to_return = [cancelled_order]
        event_bus = EventBus()

        service = SyncOrdersService(fake_marketplace_plugin, fake_order_repository, event_bus)
        result = await service.sync_new_orders()

        assert result.cancelled_orders == ()


class TestSyncPackingStarted:
    """Testy wykrywania rozpoczęcia pakowania (zmiana etapu realizacji)."""

    @pytest.mark.asyncio
    async def test_przejscie_na_processing_emituje_packing_started(
        self, fake_marketplace_plugin, fake_order_repository, sample_order
    ):
        """Zmiana fulfillment_status NEW -> PROCESSING powinna wyemitować zdarzenie."""
        from dataclasses import replace

        await fake_order_repository.save(
            replace(sample_order, fulfillment_status="NEW")
        )
        processing = replace(sample_order, fulfillment_status="PROCESSING")
        fake_marketplace_plugin.orders_to_return = [processing]
        event_bus = EventBus()
        received: list[OrderPackingStarted] = []

        async def capture(event: OrderPackingStarted) -> None:
            received.append(event)

        event_bus.subscribe(OrderPackingStarted, capture)

        service = SyncOrdersService(
            fake_marketplace_plugin, fake_order_repository, event_bus
        )
        result = await service.sync_new_orders()
        await service.publish_sync_events(result)

        assert result.packing_started_orders == (processing,)
        assert len(received) == 1
        stored = await fake_order_repository.get_by_external_id(
            sample_order.external_id
        )
        assert stored is not None and stored.fulfillment_status == "PROCESSING"

    @pytest.mark.asyncio
    async def test_przejscie_na_sent_nie_emituje_packing_started(
        self, fake_marketplace_plugin, fake_order_repository, sample_order
    ):
        """Zmiana etapu na SENT aktualizuje bazę, ale nie wyzwala SMS o pakowaniu."""
        from dataclasses import replace

        await fake_order_repository.save(
            replace(sample_order, fulfillment_status="NEW")
        )
        sent = replace(sample_order, fulfillment_status="SENT")
        fake_marketplace_plugin.orders_to_return = [sent]
        event_bus = EventBus()

        service = SyncOrdersService(
            fake_marketplace_plugin, fake_order_repository, event_bus
        )
        result = await service.sync_new_orders()

        assert result.packing_started_orders == ()
        stored = await fake_order_repository.get_by_external_id(
            sample_order.external_id
        )
        assert stored is not None and stored.fulfillment_status == "SENT"

    @pytest.mark.asyncio
    async def test_nowe_zamowienie_nie_emituje_packing_started(
        self, fake_marketplace_plugin, fake_order_repository, sample_order
    ):
        """Nowe zamówienie (nawet w PROCESSING) nie wyzwala SMS o pakowaniu."""
        from dataclasses import replace

        new_processing = replace(sample_order, fulfillment_status="PROCESSING")
        fake_marketplace_plugin.orders_to_return = [new_processing]
        event_bus = EventBus()

        service = SyncOrdersService(
            fake_marketplace_plugin, fake_order_repository, event_bus
        )
        result = await service.sync_new_orders()

        assert result.new_orders_count == 1
        assert result.packing_started_orders == ()


class TestSyncCustomerReturns:
    """Testy wykrywania zwrotów klientów podczas synchronizacji."""

    @pytest.mark.asyncio
    async def test_nowy_zwrot_jest_zapisywany_i_emituje_zdarzenie(
        self,
        fake_marketplace_plugin,
        fake_order_repository,
        fake_return_repository,
        sample_return,
    ):
        """Nowy zwrot powinien zostać zapisany i wyemitować OrderReturnCreated."""
        fake_marketplace_plugin.returns_to_return = [sample_return]
        event_bus = EventBus()
        received_events: list[OrderReturnCreated] = []

        async def capture(event: OrderReturnCreated) -> None:
            received_events.append(event)

        event_bus.subscribe(OrderReturnCreated, capture)

        service = SyncOrdersService(
            fake_marketplace_plugin,
            fake_order_repository,
            event_bus,
            fake_return_repository,
        )
        result = await service.sync_new_orders()
        await service.publish_sync_events(result)

        assert result.new_returns == (sample_return,)
        assert await fake_return_repository.exists("allegro", sample_return.external_id)
        assert len(received_events) == 1
        assert received_events[0].order_return.external_id == sample_return.external_id

    @pytest.mark.asyncio
    async def test_znany_zwrot_nie_jest_zglaszany_ponownie(
        self,
        fake_marketplace_plugin,
        fake_order_repository,
        fake_return_repository,
        sample_return,
    ):
        """Zwrot już zapisany wcześniej nie powinien generować kolejnego zdarzenia."""
        await fake_return_repository.save(sample_return)
        fake_marketplace_plugin.returns_to_return = [sample_return]
        event_bus = EventBus()

        service = SyncOrdersService(
            fake_marketplace_plugin,
            fake_order_repository,
            event_bus,
            fake_return_repository,
        )
        result = await service.sync_new_orders()

        assert result.new_returns == ()

    @pytest.mark.asyncio
    async def test_blad_pobierania_zwrotow_nie_przerywa_synchronizacji(
        self,
        fake_marketplace_plugin,
        fake_order_repository,
        fake_return_repository,
        sample_order,
    ):
        """Niedostępność API zwrotów nie może zablokować synchronizacji zamówień."""
        fake_marketplace_plugin.orders_to_return = [sample_order]
        fake_marketplace_plugin.should_raise_returns_api_error = True
        event_bus = EventBus()

        service = SyncOrdersService(
            fake_marketplace_plugin,
            fake_order_repository,
            event_bus,
            fake_return_repository,
        )
        result = await service.sync_new_orders()

        assert result.new_orders_count == 1
        assert result.new_returns == ()
