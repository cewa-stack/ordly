"""
Component Resolver - mapuje pozycję zamówienia na składniki magazynowe.

Odpowiada wyłącznie za jedno pytanie: "z jakich produktów magazynowych
(i w jakiej ilości) składa się ta oferta marketplace?". Dzięki wydzieleniu
tej odpowiedzialności StockSyncService zajmuje się samą zmianą stanów, a
reguły składania zestawów żyją w jednym, testowalnym miejscu.

Kolejność rozwiązywania:
1. Jawne mapowanie offer_links - obsługuje zestawy wieloskładnikowe
   (np. Butelka + Nakrętka + Kroplomierz), konfigurowalne przez /stock link.
2. Gdy mapowania brak - dopasowanie po SKU równym identyfikatorowi oferty
   (najprostszy przypadek: jedna oferta = jeden produkt magazynowy).
"""

from __future__ import annotations

from app.domain.entities.offer_component import OfferComponent
from app.domain.entities.product import Product
from app.domain.interfaces.inventory_repository import InventoryRepository


class ComponentResolver:
    """Rozwiązuje ofertę marketplace na listę składników magazynowych."""

    def __init__(self, inventory_repository: InventoryRepository) -> None:
        """
        Args:
            inventory_repository: Repozytorium magazynu (mapowania i produkty).
        """
        self._inventory = inventory_repository

    async def resolve(self, marketplace: str, product: Product) -> list[OfferComponent]:
        """
        Zwraca składniki magazynowe odpowiadające jednej pozycji zamówienia.

        Pusta lista oznacza, że oferty nie da się powiązać z magazynem
        (brak mapowania i brak produktu o SKU równym identyfikatorowi oferty) -
        wywołujący zgłasza taką pozycję jako niedopasowaną.
        """
        links = await self._inventory.get_offer_links(marketplace, product.external_id)
        if links:
            return links

        item = await self._inventory.get_by_sku(product.external_id)
        if item is not None:
            return [OfferComponent(sku=item.sku, quantity=1)]
        return []
