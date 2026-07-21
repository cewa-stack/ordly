"""DTO przypomnienia o niewysłanych zamówieniach (job 20:00)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.entities.order import Order


@dataclass(frozen=True, slots=True)
class ShippingReminderData:
    """
    Dane przypomnienia o zamówieniach wymagających wysyłki.

    Zwracane wyłącznie, gdy przypomnienie ma sens (były dzisiaj zamówienia
    i przynajmniej jedno nie zostało wysłane) - w przeciwnym razie serwis
    zwraca None i żadna wiadomość nie jest wysyłana.
    """

    orders_today: int
    unshipped_orders: tuple[Order, ...] = field(default=())

    @property
    def unshipped_count(self) -> int:
        """Liczba zamówień oczekujących na spakowanie i wysyłkę."""
        return len(self.unshipped_orders)
