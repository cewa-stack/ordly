"""Testy jednostkowe ReturnsService."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from app.services.returns_service import ReturnsService


class TestReturnsService:
    """Testy cienkiej warstwy odczytu zwrotów."""

    @pytest.mark.asyncio
    async def test_zwraca_puste_gdy_brak_zwrotow(self, fake_return_repository):
        """Brak zapisanych zwrotów powinien dać pustą listę, nie błąd."""
        service = ReturnsService(fake_return_repository)

        records = await service.get_recent_returns()

        assert records == []

    @pytest.mark.asyncio
    async def test_zwraca_zapisany_zwrot_jako_return_record(
        self, fake_return_repository, sample_return
    ):
        """Zapisany OrderReturn powinien wrócić jako ReturnRecord z tymi samymi danymi."""
        await fake_return_repository.save(sample_return)

        service = ReturnsService(fake_return_repository)
        records = await service.get_recent_returns()

        assert len(records) == 1
        record = records[0]
        assert record.external_id == sample_return.external_id
        assert record.marketplace == sample_return.marketplace
        assert record.order_external_id == sample_return.order_external_id
        assert record.buyer_login == sample_return.buyer_login
        assert record.status == sample_return.status
        assert record.products_summary == sample_return.products_summary
        assert record.return_date == sample_return.created_at

    @pytest.mark.asyncio
    async def test_najnowszy_zwrot_pierwszy(self, fake_return_repository, sample_return):
        """Wynik powinien być posortowany malejąco po dacie zwrotu."""
        older = replace(
            sample_return,
            external_id="RETURN-OLD",
            created_at=datetime(2026, 6, 1, 8, 0, 0),
        )
        newer = replace(
            sample_return,
            external_id="RETURN-NEW",
            created_at=datetime(2026, 7, 15, 9, 0, 0),
        )
        await fake_return_repository.save(older)
        await fake_return_repository.save(newer)

        service = ReturnsService(fake_return_repository)
        records = await service.get_recent_returns()

        assert [r.external_id for r in records] == ["RETURN-NEW", "RETURN-OLD"]
