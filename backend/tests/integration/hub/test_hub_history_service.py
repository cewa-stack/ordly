"""
Historia sprzedaży na Control Hubie - prawdziwa baza SQLite.

Ryzykowne jest to, czego Hub nie sprawdzi, bo dostaje gotowe liczby:
- polska doba (zamówienie z 0:30 to już "dziś", nie wczoraj w UTC),
- suma dnia bez anulowanych, tak jak w Statystykach,
- skoki do poprzedniego / następnego dnia ze sprzedażą (puste dni pomijane),
- dzielenie dnia na strony i odporność na złe prośby Huba.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.domain.entities.order import Order
from app.domain.entities.product import Product
from app.repositories.sqlite_order_repository import SqliteOrderRepository
from app.services.hub_history_service import (
    HISTORY_PAGE_SIZE,
    TOPIC_HISTORY_DAY,
    HubHistoryService,
)
from tests.integration.hub.conftest import RecordingPublisher, SessionScope

TODAY = date(2026, 10, 5)  # poniedziałek, czas letni (UTC+2)


@pytest.fixture
def publisher() -> RecordingPublisher:
    return RecordingPublisher()


@pytest.fixture
def history(session_scope: SessionScope, publisher: RecordingPublisher) -> HubHistoryService:
    return HubHistoryService(
        session_scope_factory=session_scope, publisher=publisher, today=lambda: TODAY
    )


async def _save(session_scope: SessionScope, *orders: Order) -> None:
    async with session_scope() as session:
        repository = SqliteOrderRepository(session)
        for order in orders:
            await repository.save(order)


def _order(
    base: Order, external_id: str, utc: datetime, amount: str, **kwargs: object
) -> Order:
    return replace(
        base,
        external_id=external_id,
        order_date=utc,
        total_amount=Decimal(amount),
        **kwargs,  # type: ignore[arg-type]
    )


class TestDzien:
    async def test_dzis_po_polsku_od_najnowszego_bez_anulowanych_w_sumie(
        self,
        history: HubHistoryService,
        publisher: RecordingPublisher,
        session_scope: SessionScope,
        sample_order: Order,
    ):
        await _save(
            session_scope,
            # 0:30 w Polsce 5.10 = 22:30 UTC 4.10 - to już dzisiejsza sprzedaż.
            _order(sample_order, "A", datetime(2026, 10, 4, 22, 30), "100"),
            _order(
                sample_order,
                "B",
                datetime(2026, 10, 5, 12, 32),
                "89.99",
                marketplace="allegro_lokalnie",
            ),
            _order(sample_order, "C", datetime(2026, 10, 5, 8, 0), "50", status="CANCELLED"),
            # 23:59 w Polsce 4.10 - wczoraj.
            _order(sample_order, "Y", datetime(2026, 10, 4, 21, 59), "999"),
        )

        await history.handle_request({})

        [day] = publisher.on(TOPIC_HISTORY_DAY)
        assert day["date"] == "2026-10-05"
        assert day["label"] == "Dziś, pon. 5.10"
        assert day["orders_count"] == 2
        assert day["revenue"] == 189.99
        assert [row["order_id"] for row in day["rows"]] == ["B", "C", "A"]
        assert day["rows"][0] == {
            "time": "14:32",
            "marketplace": "allegro_lokalnie",
            "summary": "Kubek ceramiczny x2",
            "value": 89.99,
            "buyer": "jan_kowalski",
            "order_id": "B",
            "cancelled": False,
        }
        assert day["rows"][1]["cancelled"] is True
        assert day["rows"][2]["time"] == "00:30"
        assert day["prev_date"] == "2026-10-04"
        assert day["next_date"] is None
        assert (day["page"], day["pages"]) == (0, 1)

    async def test_puste_dni_sa_pomijane_w_obie_strony(
        self,
        history: HubHistoryService,
        publisher: RecordingPublisher,
        session_scope: SessionScope,
        sample_order: Order,
    ):
        await _save(
            session_scope,
            _order(sample_order, "S1", datetime(2026, 9, 28, 10, 0), "10"),
            _order(sample_order, "S2", datetime(2026, 10, 2, 10, 0), "20"),
        )

        await history.handle_request({"date": "2026-10-02"})
        await history.handle_request({"date": "2026-09-28"})

        friday, monday = publisher.on(TOPIC_HISTORY_DAY)
        assert friday["label"] == "pt 2.10"
        assert friday["prev_date"] == "2026-09-28"
        # Po piątku nic się nie sprzedało - "nowszy dzień" to dziś.
        assert friday["next_date"] == "2026-10-05"
        assert monday["label"] == "pon. 28.09"
        assert monday["prev_date"] is None
        assert monday["next_date"] == "2026-10-02"

    async def test_dzien_bez_sprzedazy(
        self, history: HubHistoryService, publisher: RecordingPublisher
    ):
        await history.handle_request({"date": "2026-10-04"})

        [day] = publisher.on(TOPIC_HISTORY_DAY)
        assert day["label"] == "Wczoraj, niedz. 4.10"
        assert day["rows"] == []
        assert (day["orders_count"], day["revenue"], day["pages"]) == (0, 0.0, 1)
        assert day["prev_date"] is None
        assert day["next_date"] == "2026-10-05"


class TestStrony:
    async def test_dzien_dzieli_sie_na_strony(
        self,
        history: HubHistoryService,
        publisher: RecordingPublisher,
        session_scope: SessionScope,
        sample_order: Order,
    ):
        count = HISTORY_PAGE_SIZE + 2
        await _save(
            session_scope,
            *(
                _order(sample_order, f"P{i}", datetime(2026, 10, 5, 6 + i, 0), "10")
                for i in range(count)
            ),
        )

        await history.handle_request({"page": 1})
        await history.handle_request({"page": 99})

        second, clamped = publisher.on(TOPIC_HISTORY_DAY)
        assert (second["page"], second["pages"]) == (1, 2)
        assert [row["order_id"] for row in second["rows"]] == ["P1", "P0"]
        assert second["orders_count"] == count
        assert clamped["page"] == 1

    @pytest.mark.parametrize(
        "payload",
        [
            {"date": "jutro", "page": "x"},
            {"date": "2027-01-01", "page": -3},
            {"date": 20261005, "page": None},
        ],
    )
    async def test_zla_prosba_daje_dzis(
        self, history: HubHistoryService, payload: dict[str, object]
    ):
        day = await history.build_day(payload)
        assert (day["date"], day["page"]) == ("2026-10-05", 0)


class TestOpis:
    async def test_pierwszy_produkt_i_liczba_pozostalych(
        self,
        history: HubHistoryService,
        session_scope: SessionScope,
        sample_order: Order,
    ):
        products = [
            Product(
                external_id="1", name="Etui  iPhone 15", quantity=1, unit_price=Decimal("50")
            ),
            Product(external_id="2", name="Szkło", quantity=2, unit_price=Decimal("20")),
            Product(external_id="3", name="Kabel", quantity=1, unit_price=Decimal("10")),
        ]
        long_name = [replace(products[0], name="Bardzo długa nazwa produktu " * 4)]
        await _save(
            session_scope,
            _order(sample_order, "M", datetime(2026, 10, 5, 10, 0), "100", products=products),
            _order(sample_order, "L", datetime(2026, 10, 5, 9, 0), "100", products=long_name),
        )

        day = await history.build_day({})

        many, long = day["rows"]
        assert many["summary"] == "Etui iPhone 15 +2"
        assert long["summary"].endswith("…")
        assert len(long["summary"]) <= 48
