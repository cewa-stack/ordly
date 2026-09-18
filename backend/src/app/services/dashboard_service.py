"""Serwis agregujący dane na potrzeby ekranu Start aplikacji ORDLY Mobile."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from app.domain.interfaces.order_repository import OrderRepository
from app.utils.time import local_midnight_utc, local_today

_SPARKLINE_DAYS = 7


@dataclass(frozen=True, slots=True)
class DashboardSummary:
    """Zbiorczy widok stanu sklepu na dziś - jedno wywołanie zamiast czterech."""

    orders_today: int
    revenue_today: float
    orders_to_ship: int
    revenue_last_7_days: tuple[float, ...] = field(default_factory=tuple)
    trend_percent: float | None = None


async def revenue_by_local_day(
    order_repository: OrderRepository, first_day: date, last_day: date
) -> list[tuple[date, float]]:
    """
    Przychód dzień po dniu (obie granice włącznie), w POLSKICH dobach.

    Kwota dnia to różnica dwóch sum "od północy". Wcześniej grupowało to
    `date()` w SQL, które dzieli doby o północy UTC - zamówienie z 0:30
    w nocy trafiało latem do wczorajszego słupka. Kosztuje to jedno
    krótkie zapytanie na dzień, co przy tygodniu czy miesiącu nie ma
    znaczenia.
    """
    boundaries = [
        first_day + timedelta(days=offset)
        for offset in range((last_day - first_day).days + 2)
    ]
    sums = [
        await order_repository.sum_amount_since(local_midnight_utc(day)) for day in boundaries
    ]
    return [
        (boundaries[index], round(sums[index] - sums[index + 1], 2))
        for index in range(len(boundaries) - 1)
    ]


class DashboardService:
    """
    Składa dane zamówień w jedno podsumowanie.

    Istnieje wyłącznie dla ekranu Start aplikacji mobilnej - komenda
    /stats bota pobiera te same dane osobno, więc nie duplikuje logiki,
    tylko zbiera wyniki kilku zapytań w jedną odpowiedź zamiast kilku
    kolejnych rundek z telefonu.
    """

    def __init__(self, order_repository: OrderRepository) -> None:
        self._order_repository = order_repository

    async def get_summary(self) -> DashboardSummary:
        """Oblicza podsumowanie dzisiejszej sprzedaży i wysyłek."""
        today = local_today()
        today_start = local_midnight_utc(today)

        orders_today = await self._order_repository.count_since(today_start)
        unshipped_today = await self._order_repository.get_unshipped_since(today_start)

        series = tuple(
            amount
            for _, amount in await revenue_by_local_day(
                self._order_repository, today - timedelta(days=_SPARKLINE_DAYS - 1), today
            )
        )
        trend_percent = self._compute_trend(series)

        return DashboardSummary(
            orders_today=orders_today,
            revenue_today=series[-1],
            orders_to_ship=len(unshipped_today),
            revenue_last_7_days=series,
            trend_percent=trend_percent,
        )

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
