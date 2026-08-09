"""
DTO mapowania ofert marketplace na magazyn (receptury zestawów).

Oferta Allegro nie zna pojęcia "składnik" - sprzedaż jednej butelki 60 ml
zdejmuje z magazynu butelkę, kroplomierz i nakrętkę. Te struktury opisują
to powiązanie oraz jego brak: `UnmappedOffer` to oferta, która się sprzedała,
ale nie ma jeszcze receptury, więc sprzedaż nie ruszyła stanów.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class RecipeComponent:
    """Jeden składnik receptury wraz z nazwą produktu magazynowego."""

    sku: str
    name: str
    quantity: int


@dataclass(frozen=True, slots=True)
class OfferRecipe:
    """Pełna receptura jednej oferty marketplace."""

    marketplace: str
    external_product_id: str
    offer_name: str | None
    components: tuple[RecipeComponent, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SoldOffer:
    """Podsumowanie sprzedaży jednej oferty w zadanym okresie."""

    marketplace: str
    external_product_id: str
    name: str
    sold_quantity: int
    orders_count: int
    last_sold_at: datetime


@dataclass(frozen=True, slots=True)
class OfferSale:
    """Pojedyncza sprzedaż oferty w konkretnym zamówieniu."""

    order_external_id: str
    order_date: datetime
    quantity: int


@dataclass(frozen=True, slots=True)
class BackfillLine:
    """Zamówienie objęte korektą wsteczną wraz z ilością do odjęcia."""

    order_external_id: str
    order_date: datetime
    quantity: int
    already_applied: bool


@dataclass(frozen=True, slots=True)
class BackfillComponent:
    """Skutek korekty wstecznej dla jednego składnika receptury."""

    sku: str
    name: str
    current_stock: int
    quantity: int
    stock_after: int


@dataclass(frozen=True, slots=True)
class BackfillPlan:
    """
    Plan korekty wstecznej dla jednej oferty.

    Ten sam kształt służy podglądowi (`applied=False`) i potwierdzeniu
    wykonania (`applied=True`) - dzięki temu interfejs pokazuje dokładnie
    to, co zaraz się wydarzy, a potem to, co się wydarzyło.
    """

    marketplace: str
    external_product_id: str
    offer_name: str | None
    since: datetime
    lines: tuple[BackfillLine, ...] = field(default_factory=tuple)
    components: tuple[BackfillComponent, ...] = field(default_factory=tuple)
    applied: bool = False

    @property
    def pending_quantity(self) -> int:
        """Liczba sztuk oferty, które nie zostały jeszcze odjęte z magazynu."""
        return sum(line.quantity for line in self.lines if not line.already_applied)
