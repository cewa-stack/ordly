"""
Pozycja z Notion "Wyświetlanie zakończonych zwrotów jako zwrotów
wymagających obsługi".

Przyczyny: synchronizacja zapisywała zwrot raz i nigdy nie aktualizowała
jego statusu, a zbiór "zamkniętych" nie znał statusów FINISHED /
FINISHED_APT (pieniądze zwrócone) ani COMMISSION_REFUND_CLAIMED. Statusy
1:1 ze swaggerem Allegro (schemat CustomerReturn).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.api.schemas import return_out
from app.core.event_bus.bus import EventBus
from app.core.event_bus.events import OrderReturnCreated
from app.domain.returns import return_requires_action, return_status_label
from app.infrastructure.plugins.allegro.exceptions import AllegroApiError
from app.infrastructure.telegram.telegram_notifier import TelegramNotifier
from app.services.attention_service import AttentionService
from app.services.issues_service import IssuesService
from app.services.sync_orders_service import SyncOrdersService

CLOSED = [
    "FINISHED",
    "FINISHED_APT",
    "COMMISSION_REFUND_CLAIMED",
    "COMMISSION_REFUNDED",
    "REJECTED",
    "CANCELLED",
]
OPEN = [
    "CREATED",
    "DISPATCHED",
    "IN_TRANSIT",
    "DELIVERED",
    "WAREHOUSE_DELIVERED",
    "WAREHOUSE_VERIFICATION",
]


def _service(plugin, orders, returns, bus: EventBus | None = None) -> SyncOrdersService:
    return SyncOrdersService(plugin, orders, bus or EventBus(), returns)


async def _attention(plugin, orders, returns):
    return await AttentionService(orders, returns, IssuesService(plugin)).counts()


class TestStatusZwrotuPoSynchronizacji:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("closed_status", CLOSED)
    async def test_zakonczony_na_allegro_znika_z_obslugi(
        self,
        closed_status,
        fake_marketplace_plugin,
        fake_order_repository,
        fake_return_repository,
        sample_return,
    ):
        await fake_return_repository.save(sample_return)  # CREATED
        before = await _attention(
            fake_marketplace_plugin, fake_order_repository, fake_return_repository
        )
        assert before.open_returns == 1
        fake_marketplace_plugin.returns_to_return = [replace(sample_return, status=closed_status)]

        await _service(
            fake_marketplace_plugin, fake_order_repository, fake_return_repository
        ).sync_new_orders()

        assert await fake_return_repository.get_status("allegro", "RETURN-001") == closed_status
        counts = await _attention(
            fake_marketplace_plugin, fake_order_repository, fake_return_repository
        )
        assert counts.open_returns == 0
        [record] = await fake_return_repository.get_recent()
        assert return_out(record).requires_action is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize("open_status", OPEN)
    async def test_zwroty_wymagajace_dzialania_nadal_widoczne(
        self,
        open_status,
        fake_marketplace_plugin,
        fake_order_repository,
        fake_return_repository,
        sample_return,
    ):
        await fake_return_repository.save(sample_return)
        fake_marketplace_plugin.returns_to_return = [replace(sample_return, status=open_status)]

        await _service(
            fake_marketplace_plugin, fake_order_repository, fake_return_repository
        ).sync_new_orders()

        counts = await _attention(
            fake_marketplace_plugin, fake_order_repository, fake_return_repository
        )
        assert counts.open_returns == 1
        [record] = await fake_return_repository.get_recent()
        assert return_out(record).requires_action is True

    @pytest.mark.asyncio
    async def test_niepelna_odpowiedz_nie_nadpisuje_statusu(
        self, fake_marketplace_plugin, fake_order_repository, fake_return_repository, sample_return
    ):
        await fake_return_repository.save(replace(sample_return, status="FINISHED"))
        fake_marketplace_plugin.returns_to_return = [replace(sample_return, status="UNKNOWN")]

        await _service(
            fake_marketplace_plugin, fake_order_repository, fake_return_repository
        ).sync_new_orders()

        assert await fake_return_repository.get_status("allegro", "RETURN-001") == "FINISHED"

    @pytest.mark.asyncio
    async def test_blad_listy_zwrotow_nie_zmienia_danych(
        self, fake_marketplace_plugin, fake_order_repository, fake_return_repository, sample_return
    ):
        await fake_return_repository.save(replace(sample_return, status="FINISHED"))
        fake_marketplace_plugin.should_raise_returns_api_error = True

        await _service(
            fake_marketplace_plugin, fake_order_repository, fake_return_repository
        ).sync_new_orders()

        assert await fake_return_repository.get_status("allegro", "RETURN-001") == "FINISHED"


class TestPowiadomieniaOZwrotach:
    @pytest.mark.asyncio
    async def test_zwrot_zakonczony_przy_pierwszym_zobaczeniu_nie_daje_powiadomienia(
        self, fake_marketplace_plugin, fake_order_repository, fake_return_repository, sample_return
    ):
        bus = EventBus()
        received: list[OrderReturnCreated] = []

        async def capture(event: OrderReturnCreated) -> None:
            received.append(event)

        bus.subscribe(OrderReturnCreated, capture)
        fake_marketplace_plugin.returns_to_return = [
            replace(sample_return, status="COMMISSION_REFUNDED")
        ]
        service = _service(
            fake_marketplace_plugin, fake_order_repository, fake_return_repository, bus
        )

        await service.publish_sync_events(await service.sync_new_orders())
        await service.publish_sync_events(await service.sync_new_orders())

        assert received == []
        assert await fake_return_repository.exists("allegro", "RETURN-001")

    @pytest.mark.asyncio
    async def test_nowy_otwarty_zwrot_daje_dokladnie_jedno_powiadomienie(
        self, fake_marketplace_plugin, fake_order_repository, fake_return_repository, sample_return
    ):
        bus = EventBus()
        received: list[OrderReturnCreated] = []

        async def capture(event: OrderReturnCreated) -> None:
            received.append(event)

        bus.subscribe(OrderReturnCreated, capture)
        fake_marketplace_plugin.returns_to_return = [sample_return]
        service = _service(
            fake_marketplace_plugin, fake_order_repository, fake_return_repository, bus
        )

        await service.publish_sync_events(await service.sync_new_orders())
        # Kolejne odświeżenie, potem zmiana statusu - żadnego ponownego "Nowego zwrotu".
        await service.publish_sync_events(await service.sync_new_orders())
        fake_marketplace_plugin.returns_to_return = [replace(sample_return, status="FINISHED")]
        await service.publish_sync_events(await service.sync_new_orders())

        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_bot_pokazuje_ten_sam_status_co_aplikacja(self, sample_return):
        class _Bot:
            def __init__(self) -> None:
                self.messages: list[str] = []

            async def send_message(self, chat_id: int, text: str) -> None:
                self.messages.append(text)

        bot = _Bot()
        await TelegramNotifier(bot, admin_chat_id=1).notify_order_return(  # type: ignore[arg-type]
            sample_return
        )

        assert "Status: Zgłoszony" in bot.messages[0]
        assert return_status_label("CREATED") == "Zgłoszony"


class TestZwrotySpozaListy:
    @pytest.mark.asyncio
    async def test_otwarty_zwrot_spoza_listy_jest_dopytywany(
        self, fake_marketplace_plugin, fake_order_repository, fake_return_repository, sample_return
    ):
        await fake_return_repository.save(sample_return)
        fake_marketplace_plugin.returns_to_return = []
        fake_marketplace_plugin.single_returns["RETURN-001"] = replace(
            sample_return, status="FINISHED_APT"
        )

        await _service(
            fake_marketplace_plugin, fake_order_repository, fake_return_repository
        ).sync_new_orders()

        assert await fake_return_repository.get_status("allegro", "RETURN-001") == "FINISHED_APT"

    @pytest.mark.asyncio
    async def test_zamkniete_nie_sa_dopytywane(
        self, fake_marketplace_plugin, fake_order_repository, fake_return_repository, sample_return
    ):
        await fake_return_repository.save(replace(sample_return, status="COMMISSION_REFUNDED"))

        await _service(
            fake_marketplace_plugin, fake_order_repository, fake_return_repository
        ).sync_new_orders()

        assert fake_marketplace_plugin.get_return_calls == []

    @pytest.mark.asyncio
    async def test_blad_allegro_zostawia_dane_i_przerywa(
        self, fake_marketplace_plugin, fake_order_repository, fake_return_repository, sample_return
    ):
        second = replace(sample_return, external_id="RETURN-002")
        await fake_return_repository.save(sample_return)
        await fake_return_repository.save(second)
        fake_marketplace_plugin.get_return_errors["RETURN-001"] = AllegroApiError(503, "x")
        fake_marketplace_plugin.get_return_errors["RETURN-002"] = AllegroApiError(503, "x")

        await _service(
            fake_marketplace_plugin, fake_order_repository, fake_return_repository
        ).sync_new_orders()

        assert len(fake_marketplace_plugin.get_return_calls) == 1
        assert await fake_return_repository.get_status("allegro", "RETURN-001") == "CREATED"


class TestAnulowaneZamowienie:
    def test_zwrot_do_anulowanego_zamowienia_nie_wymaga_dzialania(self):
        assert return_requires_action("CREATED", order_status="CANCELLED") is False
        assert return_requires_action("CREATED", order_status="READY_FOR_PROCESSING") is True
        assert return_requires_action("CREATED", order_status=None) is True

    @pytest.mark.asyncio
    async def test_nowy_zwrot_do_anulowanego_zamowienia_bez_powiadomienia(
        self,
        fake_marketplace_plugin,
        fake_order_repository,
        fake_return_repository,
        sample_return,
        sample_order,
    ):
        await fake_order_repository.save(replace(sample_order, status="CANCELLED"))
        fake_marketplace_plugin.returns_to_return = [sample_return]

        result = await _service(
            fake_marketplace_plugin, fake_order_repository, fake_return_repository
        ).sync_new_orders()

        assert result.new_returns == ()


def test_etykiety_pokrywaja_wszystkie_statusy_ze_swaggera():
    for status in CLOSED + OPEN:
        assert return_status_label(status) != status
