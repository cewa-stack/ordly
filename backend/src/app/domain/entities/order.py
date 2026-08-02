"""Encja domenowa reprezentująca zamówienie - centralne pojęcie systemu."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.domain.entities.customer import Customer
from app.domain.entities.product import Product


@dataclass(frozen=True, slots=True)
class Order:
    """
    Zamówienie w ujęciu biznesowym, niezależne od marketplace.

    `external_id` to identyfikator zamówienia w systemie źródłowym
    (np. numer zamówienia Allegro) - w połączeniu z `marketplace`
    tworzy unikalny klucz biznesowy, odzwierciedlony przez
    unique constraint w OrderModel.

    `fulfillment_status` to etap fizycznej realizacji zamówienia
    (nowe -> pakowane -> wysłane), niezależny od `status` (płatność).
    To on zmienia się w miarę pakowania i nadawania paczki - dlatego
    opierają się na nim przypomnienia o wysyłce i SMS o pakowaniu.
    Może być None dla zamówień pobranych przed wdrożeniem tej funkcji.
    """

    external_id: str
    marketplace: str
    buyer: Customer
    products: list[Product]
    total_amount: Decimal
    currency: str
    status: str
    order_date: datetime
    fulfillment_status: str | None = None
    products_summary: str = field(init=False)

    def __post_init__(self) -> None:
        """Wylicza czytelne podsumowanie produktów do użytku w powiadomieniach."""
        summary = ", ".join(f"{p.name} x{p.quantity}" for p in self.products)
        object.__setattr__(self, "products_summary", summary or "brak danych")
