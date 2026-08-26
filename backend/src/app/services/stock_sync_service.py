"""
Automatyczna synchronizacja stanów magazynowych (Automatic Stock Synchronization).

Serwis reaguje na zdarzenia cyklu życia zamówienia (nowe zamówienie,
anulowanie, zwrot) i automatycznie koryguje stany w centralnym magazynie:

1. Nowe zamówienie   -> odejmuje sprzedane sztuki (obsługa zestawów).
2. Anulowanie        -> przywraca wcześniej odjęte sztuki.
3. Zwrot klienta     -> przywraca zwrócone sztuki.

Każda z tych zmian schodzi też na PODPRODUKTY składnika w proporcji 1:1
(butelka -> nakrętka, kroplomierz) - patrz `sub_item_cascade`. Ręczne
korekty stanu tego nie robią i robić nie mają.

Każda operacja jest chroniona znacznikiem synchronizacji
(marketplace, reference, operation) - ponowne przetworzenie tego samego
zamówienia jest pomijane, co zapobiega podwójnemu odjęciu stanów.
"""

from __future__ import annotations

from loguru import logger

from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.inventory_movement import (
    MOVEMENT_SOURCE_CANCELLATION,
    MOVEMENT_SOURCE_ORDER,
    MOVEMENT_SOURCE_RETURN,
)
from app.domain.entities.offer_component import OfferComponent
from app.domain.entities.order import Order
from app.domain.entities.order_return import OrderReturn
from app.domain.entities.product import Product
from app.domain.interfaces.inventory_repository import InventoryRepository
from app.domain.interfaces.stock_sync_repository import StockSyncRepository
from app.services.component_resolver import ComponentResolver
from app.services.stock_ledger import apply_stock_change
from app.services.sub_item_cascade import cascade_to_sub_items
from app.shared.dto.inventory_dto import StockSyncOutcome

OPERATION_DEDUCT = "DEDUCT"
OPERATION_RESTORE_CANCEL = "RESTORE_CANCEL"
OPERATION_RESTORE_RETURN = "RESTORE_RETURN"


class StockSyncService:
    """Automatycznie aktualizuje magazyn na podstawie zdarzeń zamówień."""

    def __init__(
        self,
        inventory_repository: InventoryRepository,
        stock_sync_repository: StockSyncRepository,
        component_resolver: ComponentResolver | None = None,
    ) -> None:
        """
        Args:
            inventory_repository: Repozytorium centralnego magazynu.
            stock_sync_repository: Rejestr znaczników synchronizacji
                (ochrona przed podwójnym odjęciem).
            component_resolver: Resolver składników oferty. Gdy None, tworzony
                jest domyślny na bazie inventory_repository.
        """
        self._inventory = inventory_repository
        self._sync_markers = stock_sync_repository
        self._resolver = component_resolver or ComponentResolver(inventory_repository)

    async def process_order_created(self, order: Order) -> StockSyncOutcome:
        """
        Odejmuje z magazynu produkty z nowego zamówienia.

        Operacja jest idempotentna - jeżeli zamówienie zostało już
        przetworzone, zwraca outcome z processed=False bez żadnych zmian.
        """
        marked = await self._sync_markers.mark_processed(
            order.marketplace, order.external_id, OPERATION_DEDUCT
        )
        if not marked:
            logger.debug(
                "Zamówienie {} już zsynchronizowane z magazynem - pomijam",
                order.external_id,
            )
            return StockSyncOutcome(
                processed=False,
                operation=OPERATION_DEDUCT,
                reference=order.external_id,
            )

        low_stock, unmatched = await self._apply_products(
            marketplace=order.marketplace,
            products=order.products,
            sign=-1,
            reason="Nowe zamówienie",
            source=MOVEMENT_SOURCE_ORDER,
            reference=order.external_id,
        )
        return StockSyncOutcome(
            processed=True,
            operation=OPERATION_DEDUCT,
            reference=order.external_id,
            low_stock_items=tuple(low_stock),
            unmatched_products=tuple(unmatched),
        )

    async def process_order_cancelled(self, order: Order) -> StockSyncOutcome:
        """
        Przywraca stany po anulowaniu zamówienia przed wysyłką.

        Przywrócenie następuje tylko wtedy, gdy zamówienie zostało
        wcześniej odjęte (istnieje znacznik DEDUCT) i nie zostało jeszcze
        przywrócone (brak znacznika RESTORE_CANCEL).
        """
        deducted = await self._sync_markers.was_processed(
            order.marketplace, order.external_id, OPERATION_DEDUCT
        )
        if not deducted:
            logger.debug(
                "Anulowane zamówienie {} nie było odjęte z magazynu - pomijam",
                order.external_id,
            )
            return StockSyncOutcome(
                processed=False,
                operation=OPERATION_RESTORE_CANCEL,
                reference=order.external_id,
            )

        marked = await self._sync_markers.mark_processed(
            order.marketplace, order.external_id, OPERATION_RESTORE_CANCEL
        )
        if not marked:
            return StockSyncOutcome(
                processed=False,
                operation=OPERATION_RESTORE_CANCEL,
                reference=order.external_id,
            )

        _, unmatched = await self._apply_products(
            marketplace=order.marketplace,
            products=order.products,
            sign=1,
            reason="Anulowanie zamówienia",
            source=MOVEMENT_SOURCE_CANCELLATION,
            reference=order.external_id,
        )
        return StockSyncOutcome(
            processed=True,
            operation=OPERATION_RESTORE_CANCEL,
            reference=order.external_id,
            unmatched_products=tuple(unmatched),
        )

    async def process_return(self, order_return: OrderReturn) -> StockSyncOutcome:
        """
        Przywraca stany magazynowe po zwrocie klienta.

        Idempotentne po numerze zwrotu - ten sam zwrot nigdy nie
        zwiększy stanów dwa razy.
        """
        marked = await self._sync_markers.mark_processed(
            order_return.marketplace, order_return.external_id, OPERATION_RESTORE_RETURN
        )
        if not marked:
            logger.debug(
                "Zwrot {} już zsynchronizowany z magazynem - pomijam",
                order_return.external_id,
            )
            return StockSyncOutcome(
                processed=False,
                operation=OPERATION_RESTORE_RETURN,
                reference=order_return.external_id,
            )

        _, unmatched = await self._apply_products(
            marketplace=order_return.marketplace,
            products=order_return.products,
            sign=1,
            reason="Zwrot od klienta",
            source=MOVEMENT_SOURCE_RETURN,
            reference=order_return.order_external_id,
        )
        return StockSyncOutcome(
            processed=True,
            operation=OPERATION_RESTORE_RETURN,
            reference=order_return.external_id,
            unmatched_products=tuple(unmatched),
        )

    async def _apply_products(
        self,
        marketplace: str,
        products: list[Product],
        sign: int,
        reason: str,
        source: str,
        reference: str,
    ) -> tuple[list[InventoryItem], list[str]]:
        """
        Stosuje zmianę stanów dla wszystkich produktów dokumentu wraz
        z kaskadą na podprodukty każdego składnika.

        Returns:
            Krotka (produkty z niskim stanem po operacji, produkty
            bez mapowania na magazyn). Podprodukty, które zeszły poniżej
            progu, też trafiają do pierwszej listy - próg niskiego stanu
            nakrętek pilnuje się sam, niezależnie od butelki.
        """
        low_stock: list[InventoryItem] = []
        unmatched: list[str] = []

        for product in products:
            components = await self._resolver.resolve(marketplace, product)
            if not components:
                logger.warning(
                    "Brak mapowania magazynowego dla produktu '{}' ({}) - pomijam",
                    product.name,
                    product.external_id,
                )
                unmatched.append(f"{product.name} ({product.external_id})")
                continue

            # Receptura bywa jeszcze napisana po staremu - butelka,
            # nakrętka i kroplomierz jako trzy osobne składniki. Wtedy
            # kaskada musi pominąć te, które ta receptura już odjęła,
            # inaczej nakrętka zeszłaby ze stanu dwa razy.
            recipe_skus = {component.sku for component in components}

            for component in components:
                updated = await self._apply_component_change(
                    component=component,
                    quantity=product.quantity,
                    sign=sign,
                    reason=reason,
                    source=source,
                    reference=reference,
                )
                if updated is None:
                    unmatched.append(component.sku)
                    continue
                if sign < 0 and updated.is_low_stock:
                    low_stock.append(updated)

                cascaded = await cascade_to_sub_items(
                    inventory=self._inventory,
                    parent_sku=component.sku,
                    change=sign * component.quantity * product.quantity,
                    reason=reason,
                    source=source,
                    reference=reference,
                    skip_skus=recipe_skus,
                )
                if sign < 0:
                    low_stock.extend(item for item in cascaded if item.is_low_stock)

        return low_stock, unmatched

    async def _apply_component_change(
        self,
        component: OfferComponent,
        quantity: int,
        sign: int,
        reason: str,
        source: str,
        reference: str,
    ) -> InventoryItem | None:
        """
        Zmienia stan jednego składnika i zapisuje ruch w historii.

        Returns:
            Zaktualizowany produkt lub None, gdy SKU składnika nie istnieje.
        """
        return await apply_stock_change(
            inventory=self._inventory,
            sku=component.sku,
            change=sign * component.quantity * quantity,
            reason=reason,
            source=source,
            reference=reference,
        )
