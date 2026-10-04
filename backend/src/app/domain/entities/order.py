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

    `tracking_number` pochodzi z tabeli `shipments` (zapis ręczny przez
    /tracking albo automatyczny job check_waybills_job), NIE z
    checkout-formu Allegro - `fulfillment_status` z niego nie korzysta
    i pozostaje sterowany wyłącznie przez Allegro.

    `line_items_sent` to `fulfillment.shipmentSummary.lineItemsSent`
    z checkout-formu (NONE / SOME / ALL) - "ile pozycji ma już numer
    przesyłki". Nie jest zapisywane w bazie: służy synchronizacji jako
    sygnał, że Allegro przypisało numer (np. automatycznie po wygenerowaniu
    etykiety) i trzeba go dociągnąć od razu, a nie czekać na osobny job.

    `app_status` to status ustawiony RĘCZNIE w aplikacji (Nowe / W realizacji
    / Zrealizowane / Anulowane), niezależny od Allegro; None = brak ręcznej
    zmiany. `app_status_basis` to status aplikacyjny wynikający z Allegro
    w chwili ręcznej zmiany - z niego reguła priorytetu poznaje, czy Allegro
    od tego czasu coś zmieniło. Status widoczny dla użytkownika liczy
    `app.domain.order_status.effective_app_status`. Synchronizacja z
    marketplace nigdy tych pól nie ustawia (zamówienie z Allegro ma None).
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
    tracking_number: str | None = None
    line_items_sent: str | None = None
    app_status: str | None = None
    app_status_basis: str | None = None
    app_status_changed_at: datetime | None = None
    products_summary: str = field(init=False)

    def __post_init__(self) -> None:
        """Wylicza czytelne podsumowanie produktów do użytku w powiadomieniach."""
        summary = ", ".join(f"{p.name} x{p.quantity}" for p in self.products)
        object.__setattr__(self, "products_summary", summary or "brak danych")
