"""
Rejestr anulowań i zwrotów pieniędzy na prawdziwej bazie SQLite - pozycje
z Notion "Brak automatycznego zbierania danych klientów po anulowaniu
zamówienia lub zwrocie pieniędzy", "Brak miejsca i jednolitego formatu
dla danych klientów po zwrotach" oraz "Brak danych potrzebnych do
późniejszego kontaktu z klientem".

Dane w testach są fikcyjne (repozytorium jest publiczne).
"""

from __future__ import annotations

from dataclasses import fields, replace
from datetime import datetime

import pytest

from app.database.models.customer_case_model import CustomerCaseModel
from app.domain.customer_cases import (
    KIND_BOTH,
    KIND_CANCELLATION,
    KIND_REFUND,
    REASON_BUYER_RESIGNED,
    REASON_OUT_OF_STOCK,
    SOURCE_ALLEGRO_ORDER,
    SOURCE_ALLEGRO_RETURN,
    SOURCE_APP_STATUS,
    CaseFilters,
)
from app.domain.entities.customer import Customer
from app.domain.exceptions.domain_exceptions import CustomerCaseNotFoundError
from app.repositories.sqlite_customer_case_repository import SqliteCustomerCaseRepository
from app.repositories.sqlite_order_repository import SqliteOrderRepository
from app.services.customer_case_service import CustomerCaseService, InvalidCaseValueError

CANCELLED_AT = datetime(2026, 9, 10, 12, 0)
REFUNDED_AT = datetime(2026, 9, 12, 9, 30)


@pytest.fixture
async def service(in_memory_session, sample_order):
    await SqliteOrderRepository(in_memory_session).save(sample_order)
    return CustomerCaseService(
        SqliteCustomerCaseRepository(in_memory_session), SqliteOrderRepository(in_memory_session)
    )


class TestZbieranieDanych:
    @pytest.mark.asyncio
    async def test_anulowanie_tworzy_rekord(self, service, sample_order):
        case = await service.record_cancellation(sample_order, CANCELLED_AT, SOURCE_ALLEGRO_ORDER)

        assert case.id is not None
        assert case.kind == KIND_CANCELLATION
        assert case.order_external_id == sample_order.external_id
        assert case.allegro_order_id == sample_order.external_id
        assert case.order_date == sample_order.order_date
        assert case.cancelled_at == CANCELLED_AT
        assert case.refunded_at is None
        assert case.buyer_login == "jan_kowalski"
        # Powód z Allegro dla anulowania nie przychodzi - nieuzupełnione.
        assert case.reason is None
        assert case.handling_status == "REPORTED"

    @pytest.mark.asyncio
    async def test_zwrot_pieniedzy_z_powodem_z_allegro(self, service, sample_return):
        refunded = replace(sample_return, status="FINISHED", reason_type="DONT_LIKE_IT")

        case = await service.record_refund(refunded, REFUNDED_AT)

        assert case.kind == KIND_REFUND
        assert case.source == SOURCE_ALLEGRO_RETURN
        assert case.refunded_at == REFUNDED_AT
        assert case.reason == REASON_BUYER_RESIGNED
        assert case.reason_detail == "DONT_LIKE_IT"
        history = await service.reason_history(case.id)
        assert [(h.previous_reason, h.new_reason, h.source) for h in history] == [
            (None, REASON_BUYER_RESIGNED, "allegro")
        ]

    @pytest.mark.asyncio
    async def test_anulowanie_i_zwrot_to_jeden_rekord_oba_zdarzenia(
        self, service, sample_order, sample_return
    ):
        await service.record_cancellation(sample_order, CANCELLED_AT, SOURCE_ALLEGRO_ORDER)
        case = await service.record_refund(replace(sample_return, status="FINISHED"), REFUNDED_AT)

        assert case.kind == KIND_BOTH
        assert case.cancelled_at == CANCELLED_AT and case.refunded_at == REFUNDED_AT
        assert len(await service.find(CaseFilters())) == 1

    @pytest.mark.asyncio
    async def test_ponowne_wykrycie_nie_tworzy_duplikatu(self, service, sample_order):
        first = await service.record_cancellation(sample_order, CANCELLED_AT, SOURCE_ALLEGRO_ORDER)
        again = await service.record_cancellation(
            sample_order, datetime(2026, 9, 11), SOURCE_ALLEGRO_ORDER
        )

        assert again.id == first.id
        # Pierwsza zapisana data anulowania zostaje.
        assert again.cancelled_at == CANCELLED_AT
        assert len(await service.find(CaseFilters())) == 1

    @pytest.mark.asyncio
    async def test_puste_dane_nie_nadpisuja_poprawnych(self, service, sample_order):
        await service.record_cancellation(sample_order, CANCELLED_AT, SOURCE_ALLEGRO_ORDER)
        without_login = replace(sample_order, buyer=Customer(login="nieznany"))

        case = await service.record_cancellation(
            without_login, CANCELLED_AT, SOURCE_ALLEGRO_ORDER
        )

        assert case.buyer_login == "jan_kowalski"

    @pytest.mark.asyncio
    async def test_brak_loginu_to_nieuzupelnione_a_nie_nieznany(self, service, sample_order):
        order = replace(sample_order, external_id="ORDER-X", buyer=Customer(login="nieznany"))

        case = await service.record_cancellation(order, CANCELLED_AT, SOURCE_APP_STATUS)

        assert case.buyer_login is None

    @pytest.mark.asyncio
    async def test_rekord_nie_przechowuje_danych_kontaktowych(self, service, sample_order):
        order = replace(
            sample_order,
            buyer=Customer(
                login="jan_kowalski",
                email="jan@example.com",
                first_name="Jan",
                last_name="Kowalski",
                phone_number="+48000000000",
            ),
        )
        case = await service.record_cancellation(order, CANCELLED_AT, SOURCE_ALLEGRO_ORDER)

        values = {str(getattr(case, f.name)) for f in fields(case)}
        assert "jan@example.com" not in values
        assert "+48000000000" not in values
        assert "Kowalski" not in values
        columns = set(CustomerCaseModel.__table__.columns.keys())
        assert not columns & {"buyer_email", "buyer_phone", "email", "phone", "first_name"}


class TestObslugaRecznaIHistoria:
    @pytest.mark.asyncio
    async def test_zmiana_powodu_trafia_do_historii(self, service, sample_order):
        case = await service.record_cancellation(sample_order, CANCELLED_AT, SOURCE_ALLEGRO_ORDER)

        await service.update(case.id, reason=REASON_OUT_OF_STOCK)
        updated = await service.update(case.id, handling_status="IN_PROGRESS")

        assert updated.reason == REASON_OUT_OF_STOCK
        assert updated.handling_status == "IN_PROGRESS"
        history = await service.reason_history(case.id)
        assert [(h.previous_reason, h.new_reason, h.source) for h in history] == [
            (None, REASON_OUT_OF_STOCK, "manual")
        ]

    @pytest.mark.asyncio
    async def test_powod_reczny_nie_jest_nadpisywany_przez_allegro(
        self, service, sample_order, sample_return
    ):
        case = await service.record_cancellation(sample_order, CANCELLED_AT, SOURCE_ALLEGRO_ORDER)
        await service.update(case.id, reason=REASON_OUT_OF_STOCK)

        merged = await service.record_refund(
            replace(sample_return, status="FINISHED", reason_type="DAMAGED"), REFUNDED_AT
        )

        assert merged.reason == REASON_OUT_OF_STOCK

    @pytest.mark.asyncio
    async def test_wyczyszczenie_powodu(self, service, sample_order):
        case = await service.record_cancellation(sample_order, CANCELLED_AT, SOURCE_ALLEGRO_ORDER)
        await service.update(case.id, reason=REASON_OUT_OF_STOCK)

        cleared = await service.update(case.id, clear_reason=True)

        assert cleared.reason is None
        assert len(await service.reason_history(case.id)) == 2

    @pytest.mark.asyncio
    async def test_bledne_wartosci_i_brak_rekordu(self, service, sample_order):
        case = await service.record_cancellation(sample_order, CANCELLED_AT, SOURCE_ALLEGRO_ORDER)
        with pytest.raises(InvalidCaseValueError):
            await service.update(case.id, reason="ZLY")
        with pytest.raises(InvalidCaseValueError):
            await service.update(case.id, handling_status="ZLY")
        with pytest.raises(CustomerCaseNotFoundError):
            await service.update(999, reason=REASON_OUT_OF_STOCK)


class TestFiltrowanie:
    @pytest.mark.asyncio
    async def test_filtry_data_powod_status_zrodlo(self, service, sample_order, sample_return):
        a = await service.record_cancellation(sample_order, CANCELLED_AT, SOURCE_ALLEGRO_ORDER)
        b = await service.record_cancellation(
            replace(sample_order, external_id="ORDER-002"),
            datetime(2026, 9, 20),
            SOURCE_APP_STATUS,
        )
        c = await service.record_refund(
            replace(sample_return, order_external_id="ORDER-003", status="FINISHED"),
            REFUNDED_AT,
        )
        await service.update(a.id, reason=REASON_OUT_OF_STOCK)
        await service.update(b.id, handling_status="DONE")

        async def ids(**kwargs) -> list[int]:
            return [x.id for x in await service.find(CaseFilters(**kwargs))]

        # Brak towaru - szybkie odnalezienie wszystkich takich klientów.
        assert await ids(reason=REASON_OUT_OF_STOCK) == [a.id]
        assert set(await ids(reason_missing=True)) == {b.id, c.id}
        assert await ids(handling_status="DONE") == [b.id]
        assert await ids(source=SOURCE_APP_STATUS) == [b.id]
        assert await ids(kinds=(KIND_REFUND,)) == [c.id]
        assert set(await ids(kinds=(KIND_CANCELLATION, KIND_BOTH))) == {a.id, b.id}
        assert await ids(date_from=datetime(2026, 9, 15)) == [b.id]
        assert set(await ids(date_to=datetime(2026, 9, 15))) == {a.id, c.id}
        # Od najnowszego zdarzenia.
        assert await ids() == [b.id, c.id, a.id]
