"""Encja domenowa reprezentująca produkt magazynowy (IMS)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class InventoryItem:
    """
    Produkt w centralnym magazynie ORDLY, niezależny od marketplace.

    `sku` jest unikalnym kluczem biznesowym produktu - to po nim
    odwołują się komendy /stock oraz mapowania ofert marketplace.

    Produkt może mieć produkt główny (`parent_sku`) - wtedy jego stan
    porusza się w parze ze stanem produktu głównego przy KAŻDEJ sprzedaży,
    niezależnie od oferty i serwisu (butelka -> nakrętka, kroplomierz).
    Zagnieżdżenie jest jednopoziomowe: podprodukt nie może mieć własnych
    podproduktów. Pilnuje tego `InventoryService.set_parent`.
    """

    sku: str
    name: str
    stock: int
    min_stock: int
    ean: str | None = None
    category: str | None = None
    max_stock: int | None = None
    purchase_cost: Decimal | None = None
    sale_price: Decimal | None = None
    location: str | None = None

    #: SKU produktu głównego, jeśli ten produkt jest podproduktem.
    #: Encja adresuje produkt główny po SKU, nie po identyfikatorze
    #: bazodanowym - tak jak cała reszta kodu, która nigdy nie widzi ID.
    parent_sku: str | None = None

    @property
    def is_low_stock(self) -> bool:
        """
        Czy produkt osiągnął minimalny stan magazynowy.

        Produkty bez skonfigurowanego minimum (min_stock == 0) nigdy
        nie zgłaszają ostrzeżeń - użytkownik świadomie ich nie monitoruje.
        """
        return self.min_stock > 0 and self.stock <= self.min_stock

    @property
    def status_emoji(self) -> str:
        """
        Sygnalizacja stanu: 🔴 brak (stock == 0), 🟡 na/poniżej minimum
        (ale > 0), 🟢 OK (powyżej minimum albo brak skonfigurowanego minimum).

        Celowo NIEZALEŻNE od `is_low_stock` - to osobne pojęcie używane
        przez listę zakupów i powiadomienia o niskim stanie (patrz
        InventoryService/StockSyncService), które ma swój własny próg.
        Ta właściwość odpowiada wyłącznie za kolor/emoji widoczny
        użytkownikowi.
        """
        if self.stock == 0:
            return "🔴"
        if self.min_stock > 0 and self.stock <= self.min_stock:
            return "🟡"
        return "🟢"

    @property
    def stock_value(self) -> Decimal:
        """Wartość magazynowa pozycji (stan * koszt zakupu)."""
        if self.purchase_cost is None:
            return Decimal("0")
        return self.purchase_cost * self.stock
