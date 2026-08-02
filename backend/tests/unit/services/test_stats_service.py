"""Testy jednostkowe StatsService."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from app.services.stats_service import StatsService
from app.utils.time import utc_now


class TestStatsService:
    """Testy agregacji statystyk sprzedaży."""

    @pytest.mark.asyncio
    async def test_liczy_zamowienia_z_dzisiaj(self, fake_order_repository, sample_order):
        """Zamówienie z dzisiejszą datą powinno być policzone w orders_today."""
        today_order = replace(sample_order, order_date=utc_now())
        await fake_order_repository.save(today_order)

        service = StatsService(fake_order_repository)
        summary = await service.get_summary()

        assert summary.orders_today == 1
        assert summary.total_orders == 1

    @pytest.mark.asyncio
    async def test_nie_liczy_zamowien_sprzed_wielu_dni_jako_dzisiejszych(
        self, fake_order_repository, sample_order
    ):
        """Stare zamówienie nie powinno wpływać na orders_today."""
        old_order = replace(sample_order, order_date=utc_now() - timedelta(days=10))
        await fake_order_repository.save(old_order)

        service = StatsService(fake_order_repository)
        summary = await service.get_summary()

        assert summary.orders_today == 0
        assert summary.total_orders == 1
