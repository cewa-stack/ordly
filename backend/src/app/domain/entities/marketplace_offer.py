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
    Oferta sprzedawcy pobrana z marketplace - jednostka magazynu ORDLY.

    Wszystkie pola poza `quantity_on_hand` pochodzą z API marketplace.
    `available_stock` to liczba sztuk WYSTAWIONYCH w ofercie, czyli
    deklaracja wobec kupujących; `quantity_on_hand` to liczba sztuk
    leżących na półce, wpisywana ręcznie. Te dwie liczby rozjeżdżają się
    na co dzień i mieszanie ich było głównym powodem, dla którego stany
    w ORDLY nie zgadzały się z rzeczywistością.

    `signature` to pole "sygnatura" z Allegro (`external.id`) - własne
    SKU sprzedawcy. Zostaje jako informacja w interfejsie, bo pozwala
    rozpoznać ofertę szybciej niż numer.
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

    #: Ilość na półce. None = nigdy nie wpisano (interfejs pokazuje "—").
    quantity_on_hand: int | None = None
