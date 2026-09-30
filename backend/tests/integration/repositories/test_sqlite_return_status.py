"""SqliteReturnRepository: status zwrotu, otwarte zwroty i status zamówienia."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.api.schemas import return_out
from app.repositories.sqlite_order_repository import SqliteOrderRepository
from app.repositories.sqlite_return_repository import SqliteReturnRepository


class TestStatusZwrotuWBazie:
    @pytest.mark.asyncio
    async def test_aktualizacja_statusu_i_otwarte(self, in_memory_session, sample_return):
        repository = SqliteReturnRepository(in_memory_session)
        await repository.save(sample_return)
        await repository.save(replace(sample_return, external_id="R-DONE", status="FINISHED"))
        await repository.save(
            replace(sample_return, external_id="R-LOK", marketplace="allegro_lokalnie")
        )
        await in_memory_session.commit()

        assert [r.external_id for r in await repository.get_open("allegro", 50)] == ["RETURN-001"]

        await repository.update_status("allegro", "RETURN-001", "COMMISSION_REFUNDED")
        await in_memory_session.commit()

        assert await repository.get_status("allegro", "RETURN-001") == "COMMISSION_REFUNDED"
        assert await repository.get_status("allegro", "NIE-MA") is None
        assert await repository.get_open("allegro", 50) == []

    @pytest.mark.asyncio
    async def test_zwrot_do_anulowanego_zamowienia_nie_wymaga_dzialania(
        self, in_memory_session, sample_return, sample_order
    ):
        await SqliteOrderRepository(in_memory_session).save(
            replace(sample_order, status="CANCELLED")
        )
        repository = SqliteReturnRepository(in_memory_session)
        await repository.save(sample_return)  # CREATED, zamówienie ORDER-001
        await repository.save(replace(sample_return, external_id="R-2", order_external_id="X"))
        await in_memory_session.commit()

        records = {r.external_id: r for r in await repository.get_recent()}

        assert records["RETURN-001"].order_status == "CANCELLED"
        assert return_out(records["RETURN-001"]).requires_action is False
        assert records["R-2"].order_status is None
        assert return_out(records["R-2"]).requires_action is True
        assert return_out(records["R-2"]).status_label == "Zgłoszony"
