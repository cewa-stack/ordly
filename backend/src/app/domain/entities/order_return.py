"""Encja domenowa reprezentująca zwrot produktów z zamówienia."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.entities.product import Product


@dataclass(frozen=True, slots=True)
class OrderReturn:
    """
    Zwrot klienta w ujęciu biznesowym, niezależny od marketplace.

    `external_id` to identyfikator zwrotu w systemie źródłowym
    (np. numer customer-return Allegro) - w połączeniu z `marketplace`
    tworzy unikalny klucz biznesowy, odzwierciedlony przez
    unique constraint w ReturnModel.
    """

    external_id: str
    marketplace: str
    order_external_id: str
    buyer_login: str
    products: list[Product]
    status: str
    created_at: datetime
    products_summary: str = field(init=False)

    def __post_init__(self) -> None:
        """Wylicza czytelne podsumowanie zwracanych produktów do powiadomień."""
        summary = ", ".join(f"{p.name} x{p.quantity}" for p in self.products)
        object.__setattr__(self, "products_summary", summary or "brak danych")


@dataclass(frozen=True, slots=True)
class ReturnRecord:
    """
    Zwrot odczytany z bazy do wyświetlenia (np. w `GET /api/v1/returns`).

    W odróżnieniu od `OrderReturn` (encja z pełną listą `Product`, używana
    przy synchronizacji z marketplace) - `ReturnRecord` nie ma listy
    produktów, bo `ReturnModel` celowo przechowuje tylko gotowe
    `products_summary` (patrz komentarz w database/models/return_model.py).
    """

    external_id: str
    marketplace: str
    order_external_id: str
    buyer_login: str
    status: str
    products_summary: str
    return_date: datetime
