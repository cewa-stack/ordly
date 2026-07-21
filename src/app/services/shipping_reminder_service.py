"""
Serwis przypomnienia o niewysłanych zamówieniach - logika biznesowa
zadania uruchamianego codziennie o 20:00.

Scheduler jedynie wywołuje ten serwis; cała decyzja "czy i o czym
przypomnieć" żyje tutaj. Serwis nie wie nic o Telegramie ani APScheduler.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.interfaces.order_repository import OrderRepository
from app.shared.dto.reminder_dto import ShippingReminderData
from app.utils.time import warsaw_day_start_utc


class ShippingReminderService:
    """Buduje dane przypomnienia o zamówieniach wymagających wysyłki."""

    def __init__(self, order_repository: OrderRepository) -> None:
        """
        Args:
            order_repository: Repozytorium dostępu do zamówień.
        """
        self._order_repository = order_repository

    async def build_reminder(self, now: datetime | None = None) -> ShippingReminderData | None:
        """
        Buduje dane przypomnienia dla dzisiejszych zamówień.

        Zwraca None (brak przypomnienia), gdy:
        - dziś nie wpłynęło żadne zamówienie, albo
        - wszystkie dzisiejsze zamówienia zostały już wysłane.

        W przeciwnym razie zwraca liczbę dzisiejszych zamówień oraz listę
        tych, które nadal wymagają spakowania i nadania.

        Args:
            now: Bieżący czas jako naiwny UTC (dla testów); domyślnie teraz.
        """
        day_start = warsaw_day_start_utc(now)

        orders_today = await self._order_repository.count_since(day_start)
        if orders_today == 0:
            return None

        unshipped = await self._order_repository.get_unshipped_since(day_start)
        if not unshipped:
            return None

        return ShippingReminderData(
            orders_today=orders_today,
            unshipped_orders=tuple(unshipped),
        )
