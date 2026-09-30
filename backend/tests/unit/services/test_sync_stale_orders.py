"""
Zamówienia spoza okna synchronizacji - pozycja z Notion "Nieprawidłowe
wyświetlanie zamówień ze statusem innym niż „Nowe” jako oczekujących na
spakowanie".

`get_orders` zwraca tylko najnowsze checkout-formy (limit 50). Zamówienie,
które z nich wypadło, zostawało w bazie z ostatnim widzianym etapem (NEW
albo NULL) na zawsze: wisiało w "czeka na spakowanie", w plakietce
i w porannym raporcie, choć na Allegro było dawno obsłużone.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from app.core.event_bus.bus import EventBus
from app.domain.entities.order import Order
from app.infrastructure.plugins.allegro.exceptions import AllegroApiError
from app.services.attention_service import AttentionService
from app.services.issues_service import IssuesService
from app.services.shipping_reminder_service import ShippingReminderService
from app.services.sync_orders_service import SyncOrdersService

_OLD_DATE = datetime(2026, 3, 12, 9, 0, 0)  # ~170 dni temu, jak w zgłoszeniu


def _old(sample_order: Order, external_id: str, fulfillment: str | None) -> Order:
    return replace(
        sample_order,
        external_id=external_id,
        status="READY_FOR_PROCESSING",
        fulfillment_status=fulfillment,
        order_date=_OLD_DATE,
    )


async def _sync(plugin, repository) -> None:
    service = SyncOrdersService(plugin, repository, EventBus())
    result = await service.sync_new_orders()
    await service.publish_sync_events(result)


class TestZamowieniaSpozaOkna:
    @pytest.mark.asyncio
    async def test_stare_nowe_zamowienie_wyslane_na_allegro_przestaje_byc_nowe(
        self, fake_marketplace_plugin, fake_order_repository, sample_order
    ):
        stale = _old(sample_order, "OLD-1", "NEW")
        await fake_order_repository.save(stale)
        # Lista z Allegro już go nie zawiera (wypadło z okna 50 najnowszych)...
        fake_marketplace_plugin.orders_to_return = []
        # ...ale Allegro zna jego aktualny stan.
        fake_marketplace_plugin.single_orders["OLD-1"] = replace(stale, fulfillment_status="SENT")

        await _sync(fake_marketplace_plugin, fake_order_repository)

        stored = await fake_order_repository.get_by_external_id("OLD-1")
        assert stored is not None
        assert stored.fulfillment_status == "SENT"

    @pytest.mark.asyncio
    async def test_po_synchronizacji_nie_ma_go_w_liczniku_przypomnieniu_ani_liscie(
        self, fake_marketplace_plugin, fake_order_repository, fake_return_repository, sample_order
    ):
        stale = _old(sample_order, "OLD-1", "NEW")
        await fake_order_repository.save(stale)
        fake_marketplace_plugin.single_orders["OLD-1"] = replace(
            stale, fulfillment_status="PICKED_UP"
        )

        # Przed synchronizacją - błąd ze zgłoszenia: liczy się jako nowe.
        reminder = ShippingReminderService(fake_order_repository)
        assert await reminder.build_reminder() is not None

        await _sync(fake_marketplace_plugin, fake_order_repository)

        attention = AttentionService(
            fake_order_repository, fake_return_repository, IssuesService(fake_marketplace_plugin)
        )
        counts = await attention.counts()
        assert counts.pending == 0  # licznik "X zamówień czeka na spakowanie"
        assert counts.oldest_pending_utc is None  # poranny raport
        assert await reminder.build_reminder() is None  # przypomnienie 20:00
        assert await fake_order_repository.get_new_status() == []  # lista nowych (bot)
        assert await fake_order_repository.get_active(50) == []  # czat po czyszczeniu

    @pytest.mark.asyncio
    async def test_rekord_bez_etapu_null_zostaje_uzupelniony_bez_powiadomien(
        self, fake_marketplace_plugin, fake_order_repository, fake_return_repository, sample_order
    ):
        """NULL liczył się w aplikacji jako "Nowe" - to właśnie rekord ze zgłoszenia."""
        legacy = _old(sample_order, "OLD-NULL", None)
        await fake_order_repository.save(legacy)
        fake_marketplace_plugin.single_orders["OLD-NULL"] = replace(
            legacy, fulfillment_status="PROCESSING"
        )
        service = SyncOrdersService(fake_marketplace_plugin, fake_order_repository, EventBus())

        result = await service.sync_new_orders()

        stored = await fake_order_repository.get_by_external_id("OLD-NULL")
        assert stored is not None and stored.fulfillment_status == "PROCESSING"
        # Nadrabianie historii nie może wysłać klientowi SMS-a o pakowaniu
        # zamówienia sprzed miesięcy ani powiadomienia o anulowaniu.
        assert result.packing_started_orders == ()
        assert result.cancelled_orders == ()

    @pytest.mark.asyncio
    async def test_anulowane_na_allegro_znika_i_daje_jedno_powiadomienie(
        self, fake_marketplace_plugin, fake_order_repository, sample_order
    ):
        stale = _old(sample_order, "OLD-1", "NEW")
        await fake_order_repository.save(stale)
        fake_marketplace_plugin.single_orders["OLD-1"] = replace(stale, status="CANCELLED")
        service = SyncOrdersService(fake_marketplace_plugin, fake_order_repository, EventBus())

        first = await service.sync_new_orders()
        second = await service.sync_new_orders()

        assert [o.external_id for o in first.cancelled_orders] == ["OLD-1"]
        # Kolejna synchronizacja nie duplikuje powiadomienia - anulowane
        # zamówienie nie jest już nawet kandydatem do odświeżenia.
        assert second.cancelled_orders == ()
        assert fake_marketplace_plugin.get_order_calls == ["OLD-1"]

    @pytest.mark.asyncio
    async def test_zamowienia_z_listy_nie_sa_pobierane_drugi_raz(
        self, fake_marketplace_plugin, fake_order_repository, sample_order
    ):
        order = replace(sample_order, fulfillment_status="NEW")
        await fake_order_repository.save(order)
        fake_marketplace_plugin.orders_to_return = [order]

        await _sync(fake_marketplace_plugin, fake_order_repository)

        assert fake_marketplace_plugin.get_order_calls == []

    @pytest.mark.asyncio
    async def test_zamknietych_i_z_numerem_przesylki_nie_odpytuje(
        self, fake_marketplace_plugin, fake_order_repository, sample_order
    ):
        await fake_order_repository.save(_old(sample_order, "SENT-1", "SENT"))
        await fake_order_repository.save(
            replace(_old(sample_order, "CANC-1", "NEW"), status="CANCELLED")
        )
        await fake_order_repository.save(
            replace(_old(sample_order, "TRACK-1", "NEW"), tracking_number="INPOST123")
        )
        await fake_order_repository.save(
            replace(_old(sample_order, "AL-1", "NEW"), marketplace="allegro_lokalnie")
        )

        await _sync(fake_marketplace_plugin, fake_order_repository)

        assert fake_marketplace_plugin.get_order_calls == []

    @pytest.mark.asyncio
    async def test_404_zostawia_dane_lokalne_i_idzie_dalej(
        self, fake_marketplace_plugin, fake_order_repository, sample_order
    ):
        await fake_order_repository.save(_old(sample_order, "GONE", "NEW"))
        second = replace(_old(sample_order, "OLD-2", "NEW"), order_date=datetime(2026, 3, 1))
        await fake_order_repository.save(second)
        fake_marketplace_plugin.get_order_errors["GONE"] = AllegroApiError(404, "brak")
        fake_marketplace_plugin.single_orders["OLD-2"] = replace(second, fulfillment_status="SENT")

        await _sync(fake_marketplace_plugin, fake_order_repository)

        gone = await fake_order_repository.get_by_external_id("GONE")
        old2 = await fake_order_repository.get_by_external_id("OLD-2")
        assert gone is not None and gone.fulfillment_status == "NEW"
        assert old2 is not None and old2.fulfillment_status == "SENT"

    @pytest.mark.asyncio
    async def test_awaria_allegro_nie_nadpisuje_i_przerywa_petle(
        self, fake_marketplace_plugin, fake_order_repository, sample_order
    ):
        await fake_order_repository.save(_old(sample_order, "OLD-1", "NEW"))
        await fake_order_repository.save(
            replace(_old(sample_order, "OLD-2", "NEW"), order_date=datetime(2026, 3, 1))
        )
        fake_marketplace_plugin.get_order_errors["OLD-1"] = AllegroApiError(503, "przerwa")
        fake_marketplace_plugin.single_orders["OLD-2"] = replace(
            _old(sample_order, "OLD-2", "SENT"), order_date=datetime(2026, 3, 1)
        )

        await _sync(fake_marketplace_plugin, fake_order_repository)

        old1 = await fake_order_repository.get_by_external_id("OLD-1")
        old2 = await fake_order_repository.get_by_external_id("OLD-2")
        assert old1 is not None and old1.fulfillment_status == "NEW"
        # Pętla przerwana po pierwszym błędzie sieci/5xx - nie dobijamy API.
        assert old2 is not None and old2.fulfillment_status == "NEW"
        assert fake_marketplace_plugin.get_order_calls == ["OLD-1"]

    @pytest.mark.asyncio
    async def test_zmiana_na_zywo_poza_oknem_nadal_daje_sms_o_pakowaniu(
        self, fake_marketplace_plugin, fake_order_repository, sample_order
    ):
        """Znany etap NEW -> PROCESSING to prawdziwa zmiana, a nie nadrabianie."""
        stale = _old(sample_order, "OLD-1", "NEW")
        await fake_order_repository.save(stale)
        fake_marketplace_plugin.single_orders["OLD-1"] = replace(
            stale, fulfillment_status="PROCESSING"
        )
        service = SyncOrdersService(fake_marketplace_plugin, fake_order_repository, EventBus())

        result = await service.sync_new_orders()

        assert [o.external_id for o in result.packing_started_orders] == ["OLD-1"]

    @pytest.mark.asyncio
    async def test_limit_zapytan_na_cykl(
        self, fake_marketplace_plugin, fake_order_repository, sample_order
    ):
        for index in range(40):
            await fake_order_repository.save(
                replace(
                    _old(sample_order, f"OLD-{index}", "NEW"),
                    order_date=datetime(2026, 3, 1, 0, index),
                )
            )

        await _sync(fake_marketplace_plugin, fake_order_repository)

        # Wszystkie dają 404 w fake'u (brak w single_orders) - liczy się
        # tylko to, że jeden cykl nie wysłał 40 zapytań naraz.
        assert len(fake_marketplace_plugin.get_order_calls) == 25
