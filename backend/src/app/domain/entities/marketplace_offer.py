"""Encja domenowa opisująca ofertę wystawioną na marketplace."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

#: Statusy publikacji, w których oferta może jeszcze zebrać zamówienie -
#: i jedyne, jakie trafiają do katalogu.
#:
#: `ACTIVATING` jest tu razem z `ACTIVE` celowo: to oferta w trakcie
#: wystawiania, która za chwilę zacznie sprzedawać. Pominięcie jej
#: cofnęłoby nas do problemu, który katalog rozwiązuje - powiązanie
#: dałoby się zrobić dopiero po pierwszej sprzedaży, czyli po tej, która
#: magazynu nie ruszyła.
#:
#: Krotka, nie zbiór, bo kolejność trafia wprost do query stringa
#: zapytania do Allegro i ma być powtarzalna.
ACTIVE_STATUSES: tuple[str, ...] = ("ACTIVE", "ACTIVATING")


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
