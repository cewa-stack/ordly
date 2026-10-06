"""
[FEAT-MAIL] Alert o paczce od hurtowni na Control Hubie i na telefonie.

- Hub: jeden wpis na mail (ten sam mail drugi raz nic nie dodaje, także po
  OK), własny typ `wholesale_parcel` (odróżniony od zamówień, zwrotów
  i wiadomości), pomarańczowa dioda (M3-a), zamknięcie przyciskiem OK,
  nic w ORDLY nie zamyka go samo.
- Telefon: jednorazowy push z treścią zaakceptowaną 2026-10-06, bez akcji
  „Potwierdź”; Telegram tej informacji nie dostaje (M5-a).
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.entities.wholesale_parcel import WholesaleParcelNotice
from app.infrastructure.webpush import push_payload
from app.infrastructure.webpush.web_push_notifier import PushDeliveryReport, WebPushNotifier
from app.services.hub_events_service import (
    TOPIC_EVENT_NEW,
    TOPIC_EVENT_RESOLVED,
    TOPIC_EVENT_SNAPSHOT,
    HubEventsService,
)
from tests.integration.hub.conftest import RecordingPublisher, SessionScope

NOTICE = WholesaleParcelNotice(
    message_id="<20261005124300.maikpol.test@paczkomaty.pl>",
    tracking_number="620999672171521435976372",
    wholesaler_name="F.H.P. MAIK-POL",
    received_at=datetime(2026, 10, 5, 12, 43),
)


@pytest.fixture
def publisher() -> RecordingPublisher:
    return RecordingPublisher()


@pytest.fixture
def hub(session_scope: SessionScope, publisher: RecordingPublisher) -> HubEventsService:
    return HubEventsService(session_scope_factory=session_scope, publisher=publisher)


class TestHub:
    async def test_jeden_wpis_z_wlasnym_typem(self, hub, publisher):
        await hub.on_wholesale_parcel(NOTICE)

        [message] = publisher.on(TOPIC_EVENT_NEW)
        assert message["type"] == "wholesale_parcel"
        assert message["type"] not in {"new_order", "return_requested", "message", "dispute"}
        assert message["priority"] == "amber"
        assert message["data"] == {
            "carrier": "InPost",
            "tracking_number": "620999672171521435976372",
            "wholesaler": "F.H.P. MAIK-POL",
            "summary": "F.H.P. MAIK-POL · InPost 620999672171521435976372",
        }

    async def test_ten_sam_mail_drugi_raz_nic_nie_dodaje(self, hub, publisher):
        await hub.on_wholesale_parcel(NOTICE)
        await hub.on_wholesale_parcel(NOTICE)

        assert len(publisher.on(TOPIC_EVENT_NEW)) == 1

    async def test_ok_na_hubie_zamyka_i_nie_wraca(self, hub, publisher):
        await hub.on_wholesale_parcel(NOTICE)
        event_id = publisher.on(TOPIC_EVENT_NEW)[0]["id"]

        await hub.handle_ack({"event_id": event_id})
        await hub.on_wholesale_parcel(NOTICE)
        await hub.publish_snapshot()

        assert len(publisher.on(TOPIC_EVENT_NEW)) == 1
        assert publisher.on(TOPIC_EVENT_SNAPSHOT)[-1]["events"] == []

    async def test_porzadki_nie_zamykaja_alertu_same(self, hub, publisher):
        await hub.on_wholesale_parcel(NOTICE)
        await hub.reconcile()
        await hub.publish_snapshot()

        assert publisher.on(TOPIC_EVENT_RESOLVED) == []
        assert len(publisher.on(TOPIC_EVENT_SNAPSHOT)[-1]["events"]) == 1


class _CapturingPush(WebPushNotifier):
    def __init__(self) -> None:  # bez bazy i kluczy VAPID
        self.sent: list[push_payload.PushPayload] = []

    async def _send(self, payload, *, respect_quiet_hours=True, counts=None):  # type: ignore[override]
        self.sent.append(payload)
        return PushDeliveryReport(subscriptions=1, delivered=1, expired=0, failed=0)


class TestTelefon:
    async def test_push_z_zaakceptowana_trescia(self):
        push = _CapturingPush()

        await push.notify_wholesale_parcel(NOTICE)

        [payload] = push.sent
        assert payload.title == "Paczka z hurtowni"
        assert len(payload.title) <= 24
        assert payload.body == (
            "F.H.P. MAIK-POL nadała paczkę InPost.\nNumer: 620999672171521435976372"
        )
        assert payload.url == "/start"
        assert payload.collapse_key == "parcel:620999672171521435976372"
        # Tylko „Pokaż” - żadnej akcji potwierdzenia.
        assert [action["action"] for action in payload.actions] == ["open"]

    def test_telegram_nie_ma_tej_informacji(self):
        from app.domain.interfaces.notifier import Notifier

        assert not hasattr(Notifier, "notify_wholesale_parcel")
