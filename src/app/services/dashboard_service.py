"""Serwis agregujący dane na potrzeby ekranu Start aplikacji TOOM Mobile."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.domain.interfaces.inventory_repository import InventoryRepository
from app.domain.interfaces.order_repository import OrderRepository
from app.utils.time import utc_now

_SPARKLINE_DAYS = 7


@dataclass(frozen=True, slots=True)
class DashboardSummary:
    """Zbiorczy widok stanu sklepu na dziś - jedno wywołanie zamiast czterech."""

    orders_today: int
    revenue_today: float
    orders_to_ship: int
    low_stock_count: int
    revenue_last_7_days: tuple[float, ...] = field(default_factory=tuple)
    trend_percent: float | None = None


class DashboardService:
    """
    Łączy dane zamówień i magazynu w jedno podsumowanie.

    Istnieje wyłącznie dla ekranu Start aplikacji mobilnej - komendy
    Telegram (/stats, /stock) pobierają te same dane osobno, więc nie
    duplikuje logiki, tylko składa wyniki dwóch repozytoriów w jedną
    odpowiedź zamiast kilku kolejnych zapytań z telefonu.
    """

    def __init__(
        self,
        order_repository: OrderRepository,
        inventory_repository: InventoryRepository,
    ) -> None:
        self._order_repository = order_repository
        self._inventory_repository = inventory_repository

    async def get_summary(self) -> DashboardSummary:
        """Oblicza podsumowanie dzisiejszej sprzedaży, wysyłek i niskich stanów."""
        now = utc_now()
        today_start = datetime(now.year, now.month, now.day)

        orders_today = await self._order_repository.count_since(today_start)
        revenue_today = await self._order_repository.sum_amount_since(today_start)
        unshipped_today = await self._order_repository.get_unshipped_since(today_start)
        low_stock_items = await self._inventory_repository.get_low_stock()

        series = await self._build_sparkline(today_start)
        trend_percent = self._compute_trend(series)

        return DashboardSummary(
            orders_today=orders_today,
            revenue_today=revenue_today,
            orders_to_ship=len(unshipped_today),
            low_stock_count=len(low_stock_items),
            revenue_last_7_days=series,
            trend_percent=trend_percent,
        )

    async def _build_sparkline(self, today_start: datetime) -> tuple[float, ...]:
        """
        Zwraca sprzedaż z ostatnich `_SPARKLINE_DAYS` dni (najstarszy -> dziś),
        uzupełniając dni bez zamówień zerami.
        """
        window_start = today_start - timedelta(days=_SPARKLINE_DAYS - 1)
        by_day = await self._order_repository.sum_amount_by_day(window_start)

        series: list[float] = []
        for offset in range(_SPARKLINE_DAYS):
            day = window_start + timedelta(days=offset)
            series.append(by_day.get(day.strftime("%Y-%m-%d"), 0.0))
        return tuple(series)

    @staticmethod
    def _compute_trend(series: tuple[float, ...]) -> float | None:
        """
        Procentowa zmiana sprzedaży dzisiejszej względem średniej z
        poprzednich dni w oknie. Zwraca None, gdy nie ma bazy do porównania
        (brak sprzedaży we wcześniejszych dniach) - apka pokazuje wtedy
        wartość bez trendu zamiast mylącego "+0%"/dzielenia przez zero.
        """
        if len(series) < 2:
            return None
        today_value = series[-1]
        previous_days = series[:-1]
        baseline = sum(previous_days) / len(previous_days)
        if baseline <= 0:
            return None
        return ((today_value - baseline) / baseline) * 100
