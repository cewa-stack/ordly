"""
Powiadomienia push po wdrożeniu projektu "Nokturn" (zaakceptowany 2026-09-22).

Sprawdzamy DECYZJĘ notifiera - jaka treść, czy z dźwiękiem, jaka
plakietka - a nie samą wysyłkę. `_deliver` jest podmieniony na
przechwytywacz, więc testy nie potrzebują bazy ani serwerów push.
"""

from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal

import pytest

from app.domain.entities.allegro_lokalnie_event import AllegroLokalnieEvent
from app.domain.entities.customer import Customer
from app.domain.entities.order import Order
from app.domain.entities.order_return import ReturnRecord
from app.domain.entities.product import Product
from app.infrastructure.webpush import web_push_notifier as modul
from app.infrastructure.webpush.push_payload import PushPayload
from app.infrastructure.webpush.web_push_notifier import PushDeliveryReport, WebPushNotifier
from app.services.attention_service import (
    AttentionCounts,
    AttentionService,
    is_pending_packing,
)
from app.shared.dto.reminder_dto import ShippingReminderData

# ----------------------------------------------------------------------
# Pomocnicze
# ----------------------------------------------------------------------


def _order(
    external_id: str = "A-1",
    *,
    status: str = "READY_FOR_PROCESSING",
    fulfillment: str | None = "NEW",
    tracking: str | None = None,
    when: datetime = datetime(2026, 9, 21, 15, 40),
) -> Order:
    return Order(
        external_id=external_id,
        marketplace="allegro",
        buyer=Customer(login="Kupiec99", email="k@example.com"),
        products=[Product(external_id="P", name="Butelki PET 30 ml", quantity=50,
                          unit_price=Decimal("0.61"))],
        total_amount=Decimal("30.50"),
        currency="PLN",
        status=status,
        order_date=when,
        fulfillment_status=fulfillment,
        tracking_number=tracking,
    )


class _Przechwyt(WebPushNotifier):
    """Notifier bez bazy: zapamiętuje gotowe powiadomienia zamiast je wysyłać."""

    def __init__(self, counts: AttentionCounts | None = None, *, licznik_pada: bool = False):
        async def licznik() -> AttentionCounts:
            if licznik_pada:
                raise RuntimeError("Allegro nie odpowiada")
            assert counts is not None
            return counts

        super().__init__(
            session_scope_factory=None,  # type: ignore[arg-type]
            vapid_private_key="k",
            vapid_claim_email="mailto:t@example.com",
            attention_counter=licznik if (counts is not None or licznik_pada) else None,
        )
        self.wyslane: list[PushPayload] = []

    async def _deliver(self, payload: PushPayload) -> PushDeliveryReport:
        self.wyslane.append(payload)
        return PushDeliveryReport(subscriptions=1, delivered=1, expired=0, failed=0)


def _counts(pending=3, issues: int | None = 2, returns=1, oldest=datetime(2026, 9, 21, 15, 40)):
    return AttentionCounts(
        pending=pending, open_issues=issues, open_returns=returns, oldest_pending_utc=oldest
    )


@pytest.fixture(autouse=True)
def _poza_godzinami_ciszy(monkeypatch: pytest.MonkeyPatch):
    """Południe - żeby cisza 22:00-7:00 nie zmieniała wyniku testów dźwięku."""
    monkeypatch.setattr(modul, "local_now", lambda: datetime(2026, 9, 22, 12, 0))


# ----------------------------------------------------------------------
# 1. Plakietka = "Wymaga uwagi"
# ----------------------------------------------------------------------


class TestPlakietka:
    async def test_kazde_powiadomienie_niesie_sume_z_ekranu_start(self):
        notifier = _Przechwyt(_counts(pending=3, issues=2, returns=1))

        await notifier.notify_new_order(_order())

        assert notifier.wyslane[0].badge == 6

    async def test_dyskusja_nie_wbija_juz_na_sztywno_jedynki(self):
        from app.domain.entities.dispute_notice import DisputeNotice

        notifier = _Przechwyt(_counts(pending=4, issues=1, returns=0))
        await notifier.notify_new_dispute(
            DisputeNotice(
                message_id="<m@x>", issue_id="i", buyer_login="a",
                received_at=datetime(2026, 9, 22, 11, 0), reason="niezgodny z opisem",
            )
        )

        assert notifier.wyslane[0].badge == 5

    async def test_gdy_allegro_nie_odpowiada_plakietka_zostaje_bez_zmian(self):
        notifier = _Przechwyt(licznik_pada=True)

        await notifier.notify_new_order(_order())

        # None = "nie zmieniaj" - lepiej stara liczba niż zaniżona.
        assert notifier.wyslane[0].badge is None
        assert len(notifier.wyslane) == 1  # powiadomienie i tak wyszło

    async def test_nieznana_liczba_dyskusji_nie_daje_zanizonej_plakietki(self):
        notifier = _Przechwyt(_counts(issues=None))

        await notifier.notify_new_order(_order())

        assert notifier.wyslane[0].badge is None


# ----------------------------------------------------------------------
# 2. Poranny raport zamiast wieczornego przypomnienia
# ----------------------------------------------------------------------


class TestPorannyRaport:
    async def test_godzina_liczona_lokalnie_a_nie_w_utc(self):
        # 15:40 UTC to 17:40 w Polsce (czas letni) - dawny kod pokazywał 15:40.
        notifier = _Przechwyt(_counts(oldest=datetime(2026, 9, 21, 15, 40)))

        await notifier.send_morning_brief()

        raport = notifier.wyslane[0]
        assert raport.title == "3 do spakowania"
        assert "17:40" in raport.body
        assert "15:40" not in raport.body
        assert raport.url == "/start"
        assert raport.badge == 6

    async def test_nic_nie_czeka_nic_nie_wychodzi(self):
        notifier = _Przechwyt(_counts(pending=0, issues=0, returns=0, oldest=None))

        assert await notifier.send_morning_brief() is None
        assert notifier.wyslane == []

    async def test_wieczorne_przypomnienie_nie_idzie_juz_na_telefon(self):
        notifier = _Przechwyt(_counts())

        await notifier.notify_shipping_reminder(ShippingReminderData(new_orders=(_order(),)))

        assert notifier.wyslane == []


# ----------------------------------------------------------------------
# 3-5. Anulowanie, Lokalnie po cichu, test
# ----------------------------------------------------------------------


class TestTresci:
    async def test_anulowanie_bez_loginu_z_kwota_i_po_cichu(self):
        notifier = _Przechwyt()

        await notifier.notify_order_cancelled(_order(status="CANCELLED"))

        payload = notifier.wyslane[0]
        assert payload.title == "Zamówienie anulowane"
        assert "Kupiec99" not in payload.body
        assert "30,50" in payload.body
        assert payload.silent is True

    @pytest.mark.parametrize(
        ("typ", "cicho"),
        [("order_status", True), ("return", False), ("new_order", False)],
    )
    async def test_lokalnie_dzwoni_tylko_to_co_wymaga_reakcji(self, typ: str, cicho: bool):
        notifier = _Przechwyt()

        await notifier.notify_allegro_lokalnie(
            AllegroLokalnieEvent(
                message_id="<m@allegro.pl>", event_type=typ, subject="s", snippet="",
                received_at=datetime(2026, 9, 22, 11, 0), listing_title="Butelka 10 ml",
                quantity=1, amount=Decimal("10.00"),
            )
        )

        assert notifier.wyslane[0].silent is cicho

    async def test_test_powiadomien_ma_nowy_tytul(self):
        notifier = _Przechwyt()

        await notifier.send_test()

        assert notifier.wyslane[0].title == "Powiadomienia działają"


# ----------------------------------------------------------------------
# Reguła "do spakowania" - ta sama co w aplikacjach
# ----------------------------------------------------------------------


class TestRegulaDoSpakowania:
    @pytest.mark.parametrize(
        ("zamowienie", "czeka"),
        [
            (_order(fulfillment=None), True),
            (_order(fulfillment="NEW"), True),
            (_order(fulfillment="PROCESSING"), True),
            # spakowane - czeka już tylko na kuriera
            (_order(fulfillment="READY_FOR_SHIPMENT"), False),
            (_order(fulfillment="SENT"), False),
            # numer przesyłki wykryty lokalnie, zanim Allegro zmieniło status
            (_order(fulfillment="NEW", tracking="640123"), False),
            # anulowane, choć Allegro zostawiło etap NEW
            (_order(status="CANCELLED", fulfillment="NEW"), False),
        ],
    )
    def test_zgodnie_z_desktopem(self, zamowienie: Order, czeka: bool):
        assert is_pending_packing(zamowienie) is czeka


class _Zamowienia:
    def __init__(self, orders):
        self.orders = orders
        self.limit = None

    async def get_recent(self, limit: int, offset: int = 0):
        self.limit = limit
        return self.orders[:limit]


class _Zwroty:
    def __init__(self, statuses):
        self.statuses = statuses

    async def get_recent(self, limit: int = 50, offset: int = 0):
        return [
            ReturnRecord(
                external_id=f"r{i}", marketplace="allegro", order_external_id="o",
                buyer_login="b", status=status, products_summary="x",
                return_date=datetime(2026, 9, 20),
            )
            for i, status in enumerate(self.statuses)
        ][:limit]


class _Dyskusje:
    def __init__(self, aktywne: int, pada: bool = False):
        self.aktywne, self.pada = aktywne, pada

    async def list_issues(self):
        if self.pada:
            raise RuntimeError("503")

        class _I:
            def __init__(self, active):
                self.chat_active = active

        return [_I(True)] * self.aktywne + [_I(False)]


class TestAttentionService:
    async def test_liczy_z_tych_samych_list_co_aplikacje(self):
        zamowienia = _Zamowienia(
            [_order("a"), _order("b", fulfillment="READY_FOR_SHIPMENT"), _order("c", fulfillment=None)]
        )
        service = AttentionService(
            order_repository=zamowienia,  # type: ignore[arg-type]
            return_repository=_Zwroty(["CREATED", "COMMISSION_REFUNDED", "CREATED"]),  # type: ignore[arg-type]
            issues_service=_Dyskusje(2),  # type: ignore[arg-type]
        )

        counts = await service.counts()

        assert zamowienia.limit == 100  # tyle pobiera GET /orders w obu aplikacjach
        assert (counts.pending, counts.open_issues, counts.open_returns) == (2, 2, 2)
        assert counts.badge == 6

    async def test_awaria_allegro_daje_nieznana_liczbe_dyskusji(self):
        service = AttentionService(
            order_repository=_Zamowienia([_order()]),  # type: ignore[arg-type]
            return_repository=_Zwroty([]),  # type: ignore[arg-type]
            issues_service=_Dyskusje(0, pada=True),  # type: ignore[arg-type]
        )

        counts = await service.counts()

        assert counts.open_issues is None
        assert counts.badge is None


def test_raport_wychodzi_poza_godzinami_ciszy():
    from app.infrastructure.webpush.push_payload import is_quiet_hour

    assert is_quiet_hour(time(9, 0)) is False
