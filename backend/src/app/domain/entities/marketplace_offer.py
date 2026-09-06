"""Encja domenowa opisująca ofertę wystawioną na marketplace."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

#: Statusy publikacji, w których oferta może jeszcze zebrać zamówienie.
#: `ENDED` zostaje w katalogu, bo sprzedaż sprzed zakończenia nadal
#: wymaga receptury do korekty wstecznej.
ACTIVE_STATUSES = frozenset({"ACTIVE", "ACTIVATING"})


@dataclass(frozen=True, slots=True)
class MarketplaceOffer:
    """
    Oferta sprzedawcy pobrana z marketplace (asortyment, nie sprzedaż).

    To jest brakujące ogniwo między magazynem a sprzedażą: receptury
    dowiązuje się do `external_id`, a ten identyfikator do tej pory
    dało się poznać wyłącznie z historii zamówień - czyli dopiero po
    pierwszej sprzedaży, która magazynu już nie ruszyła.

    `signature` to pole "sygnatura" z Allegro (`external.id`). Sprzedawca
    wpisuje tam zwykle własne SKU, więc jest to jedyna wskazówka
    pozwalająca powiązać ofertę z magazynem automatycznie.
    """

    marketplace: str
    external_id: str
    name: str
    signature: str | None = None
    status: str = "ACTIVE"
    available_stock: int = 0
    sold_count: int = 0
    price: Decimal | None = None
    image_url: str | None = None
    synced_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        """Mówi, czy oferta jest opublikowana i może jeszcze sprzedawać."""
        return self.status in ACTIVE_STATUSES
