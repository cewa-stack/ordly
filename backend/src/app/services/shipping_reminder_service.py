"""
Serwis przypomnienia o zamówieniach ze statusem NEW - logika biznesowa
zadania uruchamianego codziennie o 20:00.

Scheduler jedynie wywołuje ten serwis; cała decyzja "czy i o czym
przypomnieć" żyje tutaj. Serwis nie wie nic o Telegramie ani APScheduler.
"""

from __future__ import annotations

from app.domain.interfaces.order_repository import OrderRepository
from app.shared.dto.reminder_dto import ShippingReminderData


class ShippingReminderService:
    """Buduje dane przypomnienia o zamówieniach czekających na spakowanie."""

    def __init__(self, order_repository: OrderRepository) -> None:
        """
        Args:
            order_repository: Repozytorium dostępu do zamówień.
        """
        self._order_repository = order_repository

    async def build_reminder(self) -> ShippingReminderData | None:
        """
        Buduje dane przypomnienia o zamówieniach o statusie NEW.

        Sprawdza WSZYSTKIE zamówienia o statusie NEW, niezależnie od tego,
        kiedy wpłynęły - nie tylko dzisiejsze. Zamówienia w trakcie
        pakowania (PROCESSING) nie są liczone - sprzedawca już się nimi
        zajął, więc nie wymagają nagania.

        Zwraca None (brak przypomnienia), gdy nie ma ani jednego
        zamówienia o statusie NEW.
        """
        new_orders = await self._order_repository.get_new_status()
        if not new_orders:
            return None

        return ShippingReminderData(new_orders=tuple(new_orders))
