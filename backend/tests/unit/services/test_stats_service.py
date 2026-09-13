"""Testy jednostkowe StatsService."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta

import pytest

from app.services import stats_service as stats_module
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

    @pytest.mark.asyncio
    async def test_doba_zaczyna_sie_o_polnocy_w_polsce_a_nie_w_utc(
        self, fake_order_repository, sample_order, monkeypatch
    ):
        """
        13 września o 0:30 w Polsce to jeszcze 12 września 22:30 UTC.
        Liczone od północy UTC takie zamówienie wypadało z "dziś",
        a wczorajsze z 23:30 UTC (1:30 w Polsce, 13.09) wchodziło.
        """
        monkeypatch.setattr(stats_module, "local_today", lambda: date(2026, 9, 13))
        await fake_order_repository.save(
            replace(sample_order, external_id="PO-PÓŁNOCY", order_date=datetime(2026, 9, 12, 22, 30))
        )
        await fake_order_repository.save(
            replace(sample_order, external_id="WCZORAJ", order_date=datetime(2026, 9, 12, 21, 30))
        )

        summary = await StatsService(fake_order_repository).get_summary()

        assert summary.orders_today == 1

    @pytest.mark.asyncio
    async def test_anulowane_zamowienie_nie_jest_przychodem(
        self, fake_order_repository, sample_order
    ):
        await fake_order_repository.save(replace(sample_order, order_date=utc_now()))
        await fake_order_repository.save(
            replace(
                sample_order, external_id="ANULOWANE", status="CANCELLED", order_date=utc_now()
            )
        )

        summary = await StatsService(fake_order_repository).get_summary()

        assert summary.orders_today == 1
        assert summary.revenue_today == float(sample_order.total_amount)
