"""DTO przypomnienia o niewysłanych zamówieniach (job 20:00)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.entities.order import Order


@dataclass(frozen=True, slots=True)
class ShippingReminderData:
    """
    Dane przypomnienia o zamówieniach ze statusem NEW (jeszcze nietkniętych).

    Zwracane wyłącznie, gdy jest co najmniej jedno takie zamówienie,
    niezależnie od tego, kiedy wpłynęło - zamówienia w trakcie pakowania
    (PROCESSING) już nie wymagają przypomnienia. W przeciwnym razie serwis
    zwraca None i żadna wiadomość nie jest wysyłana.
    """

    new_orders: tuple[Order, ...] = field(default=())

    @property
    def new_count(self) -> int:
        """Liczba zamówień oczekujących na spakowanie (status NEW)."""
        return len(self.new_orders)
