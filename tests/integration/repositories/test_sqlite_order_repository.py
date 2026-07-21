"""
Testy integracyjne SqliteOrderRepository na prawdziwej bazie SQLite
in-memory (nie fake) - weryfikują poprawność zapytań SQL i mapowania.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from app.domain.entities.shipment import Shipment
from app.repositories.sqlite_order_repository import SqliteOrderRepository
from app.repositories.sqlite_shipment_repository import SqliteShipmentRepository

# Granica "od kiedy" niższa niż daty testowych zamówień - eliminuje zależność
# od strefy czasowej w testach zapytania o niewysłane zamówienia.
_SINCE_EPOCH = datetime(2000, 1, 1, 0, 0, 0)
_ORDER_DATE = datetime(2026, 7, 20, 10, 0, 0)


class TestSqliteOrderRepository:
    """Testy operacji CRUD i wyszukiwania na prawdziwej bazie SQLAlchemy."""

    @pytest.mark.asyncio
    async def test_zapisuje_i_odczytuje_zamowienie(self, in_memory_session, sample_order):
        """Zamówienie zapisane repozytorium powinno być odczytywalne po external_id."""
        repository = SqliteOrderRepository(in_memory_session)

        await repository.save(sample_order)
        await in_memory_session.commit()

        found = await repository.get_by_external_id(sample_order.external_id)

        assert found is not None
        assert found.external_id == sample_order.external_id
        assert found.buyer.login == sample_order.buyer.login
        assert len(found.products) == 1

    @pytest.mark.asyncio
    async def test_exists_zwraca_false_dla_niezapisanego_zamowienia(
        self, in_memory_session
    ):
        """exists() powinno zwrócić False, gdy zamówienie nigdy nie było zapisane."""
        repository = SqliteOrderRepository(in_memory_session)

        result = await repository.exists("allegro", "NIEISTNIEJACE")

        assert result is False

    @pytest.mark.asyncio
    async def test_unique_constraint_blokuje_duplikat(
        self, in_memory_session, sample_order
    ):
        """Próba zapisania tego samego (marketplace, external_id) drugi raz powinna zawieść."""
        from app.domain.exceptions.domain_exceptions import DuplicateOrderError

        repository = SqliteOrderRepository(in_memory_session)
        await repository.save(sample_order)
        await in_memory_session.commit()

        with pytest.raises(DuplicateOrderError):
            await repository.save(sample_order)

    @pytest.mark.asyncio
    async def test_duplikat_nie_wycofuje_wczesniej_zapisanych_zamowien(
        self, in_memory_session, sample_order
    ):
        """
        Naruszenie unique constraint (SAVEPOINT) nie może wycofać innych
        zamówień zapisanych w tej samej, jeszcze niezatwierdzonej transakcji.
        """
        from dataclasses import replace

        from app.domain.exceptions.domain_exceptions import DuplicateOrderError

        repository = SqliteOrderRepository(in_memory_session)
        first_order = replace(sample_order, external_id="ORDER-A")
        await repository.save(first_order)

        with pytest.raises(DuplicateOrderError):
            await repository.save(first_order)

        await in_memory_session.commit()
        assert await repository.exists("allegro", "ORDER-A")

    @pytest.mark.asyncio
    async def test_search_znajduje_po_nazwie_produktu(
        self, in_memory_session, sample_order
    ):
        """search() powinno znaleźć zamówienie po fragmencie nazwy produktu."""
        repository = SqliteOrderRepository(in_memory_session)
        await repository.save(sample_order)
        await in_memory_session.commit()

        results = await repository.search("kubek")

        assert len(results) == 1
        assert results[0].external_id == sample_order.external_id

    @pytest.mark.asyncio
    async def test_update_fulfillment_status_utrwala_etap_realizacji(
        self, in_memory_session, sample_order
    ):
        """update_fulfillment_status powinno zmienić etap realizacji w bazie."""
        repository = SqliteOrderRepository(in_memory_session)
        await repository.save(replace(sample_order, fulfillment_status="NEW"))
        await in_memory_session.commit()

        await repository.update_fulfillment_status(
            "allegro", sample_order.external_id, "PROCESSING"
        )
        await in_memory_session.commit()

        stored = await repository.get_by_external_id(sample_order.external_id)
        assert stored is not None and stored.fulfillment_status == "PROCESSING"

    @pytest.mark.asyncio
    async def test_get_unshipped_since_pomija_wyslane_anulowane_i_z_numerem(
        self, in_memory_session, sample_order
    ):
        """
        get_unshipped_since zwraca tylko zamówienia bez wysyłki: pomija
        SENT, anulowane oraz te z zapisanym numerem przewozowym.
        """
        repository = SqliteOrderRepository(in_memory_session)
        shipments = SqliteShipmentRepository(in_memory_session)

        pending = replace(
            sample_order,
            external_id="PENDING",
            fulfillment_status="NEW",
            order_date=_ORDER_DATE,
        )
        shipped = replace(
            sample_order,
            external_id="SHIPPED",
            fulfillment_status="SENT",
            order_date=_ORDER_DATE,
        )
        cancelled = replace(
            sample_order,
            external_id="CANCELLED",
            status="CANCELLED",
            fulfillment_status="NEW",
            order_date=_ORDER_DATE,
        )
        with_tracking = replace(
            sample_order,
            external_id="WITH_TRACKING",
            fulfillment_status="NEW",
            order_date=_ORDER_DATE,
        )
        for order in (pending, shipped, cancelled, with_tracking):
            await repository.save(order)
        await in_memory_session.commit()

        await shipments.save_check_result(
            "WITH_TRACKING",
            Shipment(
                order_external_id="WITH_TRACKING",
                carrier="DPD",
                tracking_number="123456",
                status="SENT",
                updated_at=None,
            ),
        )
        await in_memory_session.commit()

        unshipped = await repository.get_unshipped_since(_SINCE_EPOCH)

        assert [o.external_id for o in unshipped] == ["PENDING"]

    @pytest.mark.asyncio
    async def test_get_active_zwraca_tylko_nowe_i_pakowane(
        self, in_memory_session, sample_order
    ):
        """get_active zwraca NEW/PROCESSING, pomija SENT, anulowane i bez etapu."""
        repository = SqliteOrderRepository(in_memory_session)

        specs = [
            ("NEW-1", "NEW", "READY_FOR_PROCESSING"),
            ("PACK-1", "PROCESSING", "READY_FOR_PROCESSING"),
            ("SENT-1", "SENT", "READY_FOR_PROCESSING"),
            ("NONE-1", None, "READY_FOR_PROCESSING"),
            ("CANC-1", "NEW", "CANCELLED"),
        ]
        for external_id, fulfillment, status in specs:
            await repository.save(
                replace(
                    sample_order,
                    external_id=external_id,
                    fulfillment_status=fulfillment,
                    status=status,
                    order_date=_ORDER_DATE,
                )
            )
        await in_memory_session.commit()

        active = await repository.get_active(limit=50)

        assert {o.external_id for o in active} == {"NEW-1", "PACK-1"}

    @pytest.mark.asyncio
    async def test_mark_as_notified_ustawia_znacznik_czasu(
        self, in_memory_session, sample_order
    ):
        """Po wywołaniu mark_as_notified, notified_at nie powinno być już None."""
        from sqlalchemy import select

        from app.database.models.order_model import OrderModel

        repository = SqliteOrderRepository(in_memory_session)
        await repository.save(sample_order)
        await in_memory_session.commit()

        await repository.mark_as_notified("allegro", sample_order.external_id)
        await in_memory_session.commit()

        stmt = select(OrderModel).where(OrderModel.external_id == sample_order.external_id)
        result = await in_memory_session.execute(stmt)
        model = result.scalar_one()

        assert model.notified_at is not None
