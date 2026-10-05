"""
Most ORDLY -> Control Hub na prawdziwej bazie SQLite.

Ryzykowne jest tu to, czego Hub nie naprawi sam, bo niczego nie pamięta:
- to samo zamówienie wykryte drugi raz nie może wrócić na Hub (także po
  potwierdzeniu OK),
- zdarzenie znika z Huba, gdy sprawa zmieni się w ORDLY (pakowanie,
  anulowanie, zamknięty zwrot, numer przesyłki),
- po restarcie Huba snapshot ma dokładnie to, co wciąż czeka,
- problem z systemem trwa tak długo, jak alert w SyncFailureTracker.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.database.models.event_model import EventModel
from app.domain.entities.allegro_lokalnie_event import AllegroLokalnieEvent
from app.domain.entities.dispute_notice import DisputeNotice
from app.domain.entities.olx_event import OlxEvent
from app.domain.entities.order import Order
from app.domain.entities.order_return import OrderReturn
from app.domain.returns import ReturnStatusChange
from app.repositories.sqlite_order_repository import SqliteOrderRepository
from app.repositories.sqlite_return_repository import SqliteReturnRepository
from app.services.hub_events_service import (
    TOPIC_EVENT_NEW,
    TOPIC_EVENT_RESOLVED,
    TOPIC_EVENT_SNAPSHOT,
    TOPIC_STATS_TODAY,
    TOPIC_SYSTEM_STATUS,
    HubEventsService,
)
from app.utils.time import utc_now
from tests.integration.hub.conftest import RecordingPublisher, SessionScope


@pytest.fixture
def publisher() -> RecordingPublisher:
    return RecordingPublisher()


@pytest.fixture
def hub(session_scope: SessionScope, publisher: RecordingPublisher) -> HubEventsService:
    return HubEventsService(
        session_scope_factory=session_scope,
        publisher=publisher,
        last_sync_at=lambda: datetime(2026, 10, 4, 10, 0, 0),
    )


async def _snapshot_ids(hub: HubEventsService, publisher: RecordingPublisher) -> list[str]:
    await hub.publish_snapshot()
    return [event["id"] for event in publisher.on(TOPIC_EVENT_SNAPSHOT)[-1]["events"]]


class TestNoweZamowienie:
    async def test_wysyla_zdarzenie_w_formacie_ze_specyfikacji(
        self, hub: HubEventsService, publisher: RecordingPublisher, sample_order: Order
    ):
        await hub.on_order_created(sample_order)

        [message] = publisher.on(TOPIC_EVENT_NEW)
        assert message["id"] == "evt_1"
        assert message["type"] == "new_order"
        assert message["priority"] == "red"
        assert message["ts"].endswith(("+02:00", "+01:00"))
        assert message["data"] == {
            "order_id": "ORDER-001",
            "marketplace": "allegro",
            "value": 39.98,
            "buyer": "jan_kowalski",
            "summary": "Kubek ceramiczny x2",
        }

    async def test_drugie_wykrycie_nie_tworzy_duplikatu(
        self, hub: HubEventsService, publisher: RecordingPublisher, sample_order: Order
    ):
        await hub.on_order_created(sample_order)
        await hub.on_order_created(sample_order)

        assert len(publisher.on(TOPIC_EVENT_NEW)) == 1

    async def test_pakowanie_zamyka_zdarzenie(
        self, hub: HubEventsService, publisher: RecordingPublisher, sample_order: Order
    ):
        await hub.on_order_created(sample_order)
        await hub.on_order_closed(sample_order)

        assert publisher.on(TOPIC_EVENT_RESOLVED) == [
            {"event_id": "evt_1", "reason": "status_changed"}
        ]
        assert await _snapshot_ids(hub, publisher) == []

    async def test_zamkniecie_nieznanego_zamowienia_nic_nie_wysyla(
        self, hub: HubEventsService, publisher: RecordingPublisher, sample_order: Order
    ):
        await hub.on_order_closed(sample_order)

        assert publisher.on(TOPIC_EVENT_RESOLVED) == []


class TestPotwierdzenieOk:
    async def test_ok_zamyka_i_zapisuje_w_audycie(
        self,
        hub: HubEventsService,
        publisher: RecordingPublisher,
        session_scope: SessionScope,
        sample_order: Order,
    ):
        await hub.on_order_created(sample_order)

        await hub.handle_ack({"event_id": "evt_1", "action": "acknowledged"})

        assert await _snapshot_ids(hub, publisher) == []
        async with session_scope() as session:
            rows = (
                (
                    await session.execute(
                        select(EventModel).where(
                            EventModel.event_type == "HubEventAcknowledged"
                        )
                    )
                )
                .scalars()
                .all()
            )
        assert len(rows) == 1

    async def test_potwierdzone_zamowienie_nie_wraca_po_ponownym_wykryciu(
        self, hub: HubEventsService, publisher: RecordingPublisher, sample_order: Order
    ):
        await hub.on_order_created(sample_order)
        await hub.handle_ack({"event_id": "evt_1"})

        await hub.on_order_created(sample_order)

        assert len(publisher.on(TOPIC_EVENT_NEW)) == 1
        assert await _snapshot_ids(hub, publisher) == []

    @pytest.mark.parametrize(
        "bad", [{}, {"event_id": 1}, {"event_id": "evt_x"}, {"event_id": "40"}]
    )
    async def test_smieci_z_sieci_sa_ignorowane(
        self, hub: HubEventsService, publisher: RecordingPublisher, sample_order: Order, bad
    ):
        await hub.on_order_created(sample_order)

        await hub.handle_ack(bad)

        assert await _snapshot_ids(hub, publisher) == ["evt_1"]

    async def test_podwojne_ok_nic_nie_psuje(
        self, hub: HubEventsService, publisher: RecordingPublisher, sample_order: Order
    ):
        await hub.on_order_created(sample_order)
        await hub.handle_ack({"event_id": "evt_1"})
        await hub.handle_ack({"event_id": "evt_1"})
        await hub.handle_ack({"event_id": "evt_99"})

        assert await _snapshot_ids(hub, publisher) == []


class TestZwrotyIWiadomosci:
    async def test_zwrot_pomaranczowy_i_znika_po_zamknieciu(
        self, hub: HubEventsService, publisher: RecordingPublisher, sample_return: OrderReturn
    ):
        await hub.on_return_created(sample_return)
        [message] = publisher.on(TOPIC_EVENT_NEW)
        assert (message["type"], message["priority"]) == ("return_requested", "amber")
        assert message["data"]["value"] == 19.99

        change = ReturnStatusChange(
            external_id="RETURN-001",
            marketplace="allegro",
            order_external_id="ORDER-001",
            previous_status="CREATED",
            new_status="FINISHED",
            source="sync",
            changed_at=datetime(2026, 10, 4, 12, 0),
        )
        await hub.on_return_status_changed(change)

        assert publisher.on(TOPIC_EVENT_RESOLVED)[0]["event_id"] == message["id"]

    async def test_dyskusja_pomaranczowa(
        self, hub: HubEventsService, publisher: RecordingPublisher
    ):
        notice = DisputeNotice(
            message_id="<m1>",
            issue_id="ISSUE-1",
            buyer_login="kupujacy",
            received_at=datetime(2026, 10, 4, 9, 0),
            reason="Produkt uszkodzony",
        )
        await hub.on_dispute(notice)

        [message] = publisher.on(TOPIC_EVENT_NEW)
        assert (message["type"], message["priority"]) == ("dispute", "amber")
        assert message["data"]["summary"] == "Produkt uszkodzony"

    async def test_allegro_lokalnie_wiadomosc_tak_obserwowanie_nie(
        self, hub: HubEventsService, publisher: RecordingPublisher
    ):
        base = AllegroLokalnieEvent(
            message_id="<al1>",
            event_type="new_message",
            subject="Nowa wiadomość",
            snippet="",
            received_at=datetime(2026, 10, 4, 9, 0),
            listing_title="Lampka nocna",
        )
        await hub.on_allegro_lokalnie(base)
        await hub.on_allegro_lokalnie(replace(base, message_id="<al2>", event_type="interest"))

        [message] = publisher.on(TOPIC_EVENT_NEW)
        assert (message["type"], message["priority"]) == ("message", "amber")
        assert message["data"]["marketplace"] == "allegro_lokalnie"

    async def test_sprzedaz_olx_czerwona_bez_kwoty(
        self, hub: HubEventsService, publisher: RecordingPublisher
    ):
        event = OlxEvent(
            message_id="<olx1>",
            event_type="new_order",
            subject="Sprzedano",
            snippet="",
            received_at=datetime(2026, 10, 4, 9, 0),
            listing_title="Rower",
        )
        await hub.on_olx(event)

        [message] = publisher.on(TOPIC_EVENT_NEW)
        assert (message["type"], message["priority"]) == ("new_order", "red")
        assert "value" not in message["data"]


class TestPorzadki:
    async def test_zamowienie_z_numerem_przesylki_znika(
        self,
        hub: HubEventsService,
        publisher: RecordingPublisher,
        session_scope: SessionScope,
        sample_order: Order,
    ):
        order = replace(sample_order, fulfillment_status="NEW")
        async with session_scope() as session:
            await SqliteOrderRepository(session).save(order)
        await hub.on_order_created(order)

        await hub.reconcile()
        assert publisher.on(TOPIC_EVENT_RESOLVED) == []

        async with session_scope() as session:
            await SqliteOrderRepository(session).update_fulfillment_status(
                "allegro", "ORDER-001", "SENT"
            )
        await hub.reconcile()

        assert publisher.on(TOPIC_EVENT_RESOLVED) == [
            {"event_id": "evt_1", "reason": "status_changed"}
        ]

    async def test_zamkniety_zwrot_znika(
        self,
        hub: HubEventsService,
        publisher: RecordingPublisher,
        session_scope: SessionScope,
        sample_return: OrderReturn,
    ):
        async with session_scope() as session:
            await SqliteReturnRepository(session).save(sample_return)
        await hub.on_return_created(sample_return)
        async with session_scope() as session:
            await SqliteReturnRepository(session).update_status(
                "allegro", "RETURN-001", "REJECTED"
            )

        await hub.reconcile()

        assert len(publisher.on(TOPIC_EVENT_RESOLVED)) == 1


class TestProblemZSystemem:
    async def test_trwa_do_powrotu_kanalu_i_wraca_przy_kolejnej_awarii(
        self, hub: HubEventsService, publisher: RecordingPublisher
    ):
        await hub.sync_system_problems({"allegro"})
        await hub.sync_system_problems({"allegro"})
        [first] = publisher.on(TOPIC_EVENT_NEW)
        assert (first["type"], first["priority"]) == ("system_problem", "blue")
        assert first["data"]["summary"] == "Allegro nie odpowiada"

        await hub.sync_system_problems(set())
        assert publisher.on(TOPIC_EVENT_RESOLVED) == [
            {"event_id": first["id"], "reason": "recovered"}
        ]

        await hub.sync_system_problems({"allegro"})
        assert len(publisher.on(TOPIC_EVENT_NEW)) == 2
        assert await _snapshot_ids(hub, publisher) == [first["id"]]

    async def test_potwierdzony_problem_wraca_dopiero_przy_nowej_awarii(
        self, hub: HubEventsService, publisher: RecordingPublisher
    ):
        await hub.sync_system_problems({"poczta"})
        await hub.handle_ack({"event_id": "evt_1"})

        # Ta sama seria awarii (job co minutę) - OK już ją potwierdziło.
        await hub.sync_system_problems({"poczta"})
        assert len(publisher.on(TOPIC_EVENT_NEW)) == 1
        await hub.publish_system_status()
        assert publisher.on(TOPIC_SYSTEM_STATUS)[-1]["problems"] == []

        # Poczta wróciła (bez komunikatu - Hub już nic nie pokazuje), potem znowu padła.
        await hub.sync_system_problems(set())
        assert publisher.on(TOPIC_EVENT_RESOLVED) == []
        await hub.sync_system_problems({"poczta"})

        assert len(publisher.on(TOPIC_EVENT_NEW)) == 2
        await hub.publish_system_status()
        assert publisher.on(TOPIC_SYSTEM_STATUS)[-1]["problems"] == ["Poczta nie odpowiada"]


class TestHubOnline:
    async def test_online_dostaje_snapshot_statystyki_i_stan(
        self, hub: HubEventsService, publisher: RecordingPublisher, sample_order: Order
    ):
        await hub.on_order_created(sample_order)

        await hub.handle_hub_status({"online": True, "fw_version": "1.0.0"})

        [snapshot] = publisher.on(TOPIC_EVENT_SNAPSHOT)
        assert snapshot["total"] == 1
        assert [e["id"] for e in snapshot["events"]] == ["evt_1"]
        assert len(publisher.on(TOPIC_STATS_TODAY)) == 1
        [status] = publisher.on(TOPIC_SYSTEM_STATUS)
        assert status["last_sync_at"] == "2026-10-04T12:00:00+02:00"

    async def test_offline_niczego_nie_wysyla(
        self, hub: HubEventsService, publisher: RecordingPublisher
    ):
        await hub.handle_hub_status({"online": False})

        assert publisher.messages == []

    async def test_retained_tylko_dla_stanu_i_statystyk(
        self, hub: HubEventsService, publisher: RecordingPublisher, sample_order: Order
    ):
        await hub.on_order_created(sample_order)
        await hub.handle_hub_status({"online": True})

        retained = {topic for topic, _, retain in publisher.messages if retain}
        assert retained == {TOPIC_STATS_TODAY, TOPIC_SYSTEM_STATUS}


class TestStatystyki:
    async def test_dzisiejsza_sprzedaz_i_porownanie_z_wczoraj_o_tej_porze(
        self,
        hub: HubEventsService,
        publisher: RecordingPublisher,
        session_scope: SessionScope,
        sample_order: Order,
    ):
        now = utc_now()
        async with session_scope() as session:
            repository = SqliteOrderRepository(session)
            await repository.save(
                replace(
                    sample_order, external_id="T1", order_date=now, total_amount=Decimal("150")
                )
            )
            await repository.save(
                replace(
                    sample_order, external_id="T2", order_date=now, total_amount=Decimal("50")
                )
            )
            # Wczoraj, godzinę wcześniej niż teraz - liczy się do porównania.
            await repository.save(
                replace(
                    sample_order,
                    external_id="Y1",
                    order_date=now - timedelta(days=1, hours=1),
                    total_amount=Decimal("100"),
                )
            )

        await hub.publish_stats()

        [stats] = publisher.on(TOPIC_STATS_TODAY)
        assert stats["orders"] >= 2
        if stats["orders"] == 2:  # test nie trafił w północ
            assert stats["revenue"] == 200.0
            assert stats["avg_order"] == 100.0
            assert stats["vs_yesterday_pct"] == 100
