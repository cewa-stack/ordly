"""Serwis generowania statystyk sprzedaży dla komendy /stats."""

from __future__ import annotations

from datetime import datetime

from app.domain.interfaces.order_repository import OrderRepository
from app.shared.dto.stats_dto import StatsSummary
from app.utils.time import utc_now


class StatsService:
    """Agreguje dane zamówień w czytelne podsumowanie statystyczne."""

    def __init__(self, order_repository: OrderRepository) -> None:
        self._order_repository = order_repository

    async def get_summary(self) -> StatsSummary:
        """Oblicza statystyki: zamówienia i przychód dziś / w tym miesiącu / łącznie."""
        now = utc_now()
        today_start = datetime(now.year, now.month, now.day)
        month_start = datetime(now.year, now.month, 1)

        return StatsSummary(
            orders_today=await self._order_repository.count_since(today_start),
            orders_this_month=await self._order_repository.count_since(month_start),
            revenue_today=await self._order_repository.sum_amount_since(today_start),
            revenue_this_month=await self._order_repository.sum_amount_since(month_start),
            total_orders=await self._order_repository.count_all(),
        )
