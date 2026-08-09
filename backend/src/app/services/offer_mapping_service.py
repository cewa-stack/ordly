"""
Mapowanie ofert marketplace na magazyn (receptury) i korekta wsteczna.

Automatyczne odejmowanie stanów działa tylko dla ofert, które mają
recepturę - bez niej `ComponentResolver` nie wie, co zdjąć z półki, więc
sprzedaż przechodzi obok magazynu. Ten serwis odpowiada za trzy rzeczy:

1. Pokazanie ofert, które się sprzedają, ale receptury nie mają.
2. Zapis receptury (oferta -> lista składników z ilościami).
3. Korektę wsteczną: odjęcie sprzedaży, która przeszła zanim receptura
   powstała - rozliczaną per zamówienie, więc bezpieczną do powtórzenia.
"""

from __future__ import annotations

from datetime import timedelta

from loguru import logger

from app.domain.entities.inventory_movement import MOVEMENT_SOURCE_ORDER
from app.domain.entities.offer_component import OfferComponent
from app.domain.exceptions.domain_exceptions import InventoryItemNotFoundError
from app.domain.interfaces.inventory_repository import InventoryRepository
from app.domain.interfaces.order_repository import OrderRepository
from app.services.stock_ledger import apply_stock_change
from app.shared.dto.offer_mapping_dto import (
    BackfillComponent,
    BackfillLine,
    BackfillPlan,
    OfferRecipe,
    RecipeComponent,
    SoldOffer,
)
from app.utils.time import utc_now

DEFAULT_LOOKBACK_DAYS = 90
BACKFILL_REASON = "Korekta wsteczna - powiązanie oferty"


def backfill_reference(order_external_id: str, external_product_id: str) -> str:
    """
    Buduje referencję ruchu korekty wstecznej: numer zamówienia + oferta.

    Sam numer zamówienia nie wystarcza. Jedno zamówienie potrafi zawierać
    dwie różne oferty dzielące ten sam składnik (np. butelka 30 ml i 60 ml
    z tą samą nakrętką) - gdyby obie zapisywały ruch pod samym numerem
    zamówienia, korekta drugiej oferty uznałaby je za już rozliczone
    i cicho pominęła należne sztuki.
    """
    return f"{order_external_id}#{external_product_id}"


def _is_settled(
    references: set[str], order_external_id: str, external_product_id: str
) -> bool:
    """
    Mówi, czy dana oferta w danym zamówieniu zdjęła już ten składnik.

    Uznajemy dwa dowody: ruch spisany wcześniejszą korektą wsteczną tej
    oferty oraz ruch spisany na bieżąco przez `StockSyncService` (ten
    zapisuje sam numer zamówienia).
    """
    return (
        backfill_reference(order_external_id, external_product_id) in references
        or order_external_id in references
    )


class OfferMappingService:
    """Zarządza recepturami ofert i nadrabia stany sprzed ich powstania."""

    def __init__(
        self,
        inventory_repository: InventoryRepository,
        order_repository: OrderRepository,
    ) -> None:
        """
        Args:
            inventory_repository: Repozytorium magazynu (receptury, stany).
            order_repository: Repozytorium zamówień (sprzedaż ofert).
        """
        self._inventory = inventory_repository
        self._orders = order_repository

    async def get_recipes(self, days: int = DEFAULT_LOOKBACK_DAYS) -> list[OfferRecipe]:
        """
        Zwraca wszystkie receptury, uzupełnione o nazwę oferty z historii
        sprzedaży (sam identyfikator oferty nic nie mówi człowiekowi).
        """
        recipes = await self._inventory.get_all_offer_links()
        names = await self._offer_names(days)
        return [
            OfferRecipe(
                marketplace=recipe.marketplace,
                external_product_id=recipe.external_product_id,
                offer_name=names.get(
                    (recipe.marketplace, recipe.external_product_id), recipe.offer_name
                ),
                components=recipe.components,
            )
            for recipe in recipes
        ]

    async def get_unmapped_offers(self, days: int = DEFAULT_LOOKBACK_DAYS) -> list[SoldOffer]:
        """
        Zwraca oferty sprzedane w ostatnich `days` dniach, których sprzedaż
        NIE rusza magazynu.

        Kryterium jest dokładnie tym, którego używa `ComponentResolver`:
        oferta jest powiązana, gdy ma recepturę albo gdy istnieje produkt
        magazynowy o SKU równym identyfikatorowi oferty.
        """
        since = utc_now() - timedelta(days=days)
        sold = await self._orders.get_sold_offers_since(since)
        mapped = {
            (recipe.marketplace, recipe.external_product_id)
            for recipe in await self._inventory.get_all_offer_links()
        }

        unmapped: list[SoldOffer] = []
        for offer in sold:
            if (offer.marketplace, offer.external_product_id) in mapped:
                continue
            if await self._inventory.get_by_sku(offer.external_product_id) is not None:
                continue
            unmapped.append(offer)
        return unmapped

    async def set_recipe(
        self, marketplace: str, external_product_id: str, components: list[OfferComponent]
    ) -> OfferRecipe:
        """
        Zapisuje pełną recepturę oferty, zastępując poprzednią.

        Raises:
            InventoryItemNotFoundError: Gdy któreś SKU nie istnieje.
            ValueError: Gdy lista jest pusta, ilość jest mniejsza od 1
                albo to samo SKU powtarza się w recepturze.
        """
        if not components:
            raise ValueError("Receptura musi mieć co najmniej jeden składnik")
        if any(component.quantity < 1 for component in components):
            raise ValueError("Ilość składnika musi być większa od zera")

        skus = [component.sku for component in components]
        if len(set(skus)) != len(skus):
            raise ValueError("Ten sam produkt nie może wystąpić w recepturze dwa razy")

        await self._inventory.replace_offer_links(marketplace, external_product_id, components)
        logger.info(
            "Receptura oferty {} ustawiona na {} składnik(i)",
            external_product_id,
            len(components),
        )
        return await self._describe_recipe(marketplace, external_product_id)

    async def delete_recipe(self, marketplace: str, external_product_id: str) -> int:
        """Usuwa recepturę oferty. Zwraca liczbę usuniętych składników."""
        return await self._inventory.remove_offer_links(marketplace, external_product_id)

    async def plan_backfill(
        self,
        marketplace: str,
        external_product_id: str,
        days: int = DEFAULT_LOOKBACK_DAYS,
    ) -> BackfillPlan:
        """
        Buduje podgląd korekty wstecznej: które zamówienia zostaną
        rozliczone i jak zmieni się stan każdego składnika.

        Zamówienia, które mają już ruch magazynowy dla danego składnika,
        są oznaczone `already_applied` i pomijane w wyliczeniu.

        Raises:
            ValueError: Gdy oferta nie ma jeszcze receptury.
        """
        return await self._build_plan(marketplace, external_product_id, days, apply=False)

    async def apply_backfill(
        self,
        marketplace: str,
        external_product_id: str,
        days: int = DEFAULT_LOOKBACK_DAYS,
    ) -> BackfillPlan:
        """
        Wykonuje korektę wsteczną wyliczoną przez `plan_backfill`.

        Każde nadrobione zamówienie dostaje własny wpis w historii ruchów
        z numerem zamówienia jako referencją - dzięki temu powtórne
        uruchomienie korekty nie odejmie tych samych sztuk drugi raz.

        Raises:
            ValueError: Gdy oferta nie ma jeszcze receptury.
        """
        return await self._build_plan(marketplace, external_product_id, days, apply=True)

    async def _build_plan(
        self, marketplace: str, external_product_id: str, days: int, apply: bool
    ) -> BackfillPlan:
        """Wspólny rdzeń podglądu i wykonania korekty wstecznej."""
        components = await self._inventory.get_offer_links(marketplace, external_product_id)
        if not components:
            raise ValueError(
                "Oferta nie ma receptury - najpierw przypisz składniki magazynowe"
            )

        since = utc_now() - timedelta(days=days)
        sales = await self._orders.get_offer_sales(marketplace, external_product_id, since)
        names = await self._offer_names(days)

        # Zamówienie uznajemy za rozliczone, gdy KAŻDY składnik receptury
        # ma już dla niego ruch magazynowy. Częściowe rozliczenie (np. SKU
        # dodane do receptury później) trzeba dokończyć, a nie pominąć.
        applied_references: dict[str, set[str]] = {}
        for component in components:
            applied_references[component.sku] = await self._inventory.get_movement_references(
                component.sku
            )

        lines: list[BackfillLine] = []
        pending_by_sku: dict[str, int] = {component.sku: 0 for component in components}
        for sale in sales:
            missing = [
                component
                for component in components
                if not _is_settled(
                    applied_references[component.sku],
                    sale.order_external_id,
                    external_product_id,
                )
            ]
            lines.append(
                BackfillLine(
                    order_external_id=sale.order_external_id,
                    order_date=sale.order_date,
                    quantity=sale.quantity,
                    already_applied=not missing,
                )
            )
            for component in missing:
                pending_by_sku[component.sku] += component.quantity * sale.quantity

        plan_components: list[BackfillComponent] = []
        for component in components:
            item = await self._inventory.get_by_sku(component.sku)
            if item is None:
                continue
            quantity = pending_by_sku[component.sku]
            plan_components.append(
                BackfillComponent(
                    sku=item.sku,
                    name=item.name,
                    current_stock=item.stock,
                    quantity=quantity,
                    stock_after=max(item.stock - quantity, 0),
                )
            )

        if apply:
            await self._apply_lines(external_product_id, components, lines, applied_references)

        return BackfillPlan(
            marketplace=marketplace,
            external_product_id=external_product_id,
            offer_name=names.get((marketplace, external_product_id)),
            since=since,
            lines=tuple(lines),
            components=tuple(plan_components),
            applied=apply,
        )

    async def _apply_lines(
        self,
        external_product_id: str,
        components: list[OfferComponent],
        lines: list[BackfillLine],
        applied_references: dict[str, set[str]],
    ) -> None:
        """Zapisuje ruchy magazynowe dla zamówień jeszcze nierozliczonych."""
        for line in lines:
            if line.already_applied:
                continue
            for component in components:
                if _is_settled(
                    applied_references[component.sku],
                    line.order_external_id,
                    external_product_id,
                ):
                    continue
                await apply_stock_change(
                    inventory=self._inventory,
                    sku=component.sku,
                    change=-component.quantity * line.quantity,
                    reason=BACKFILL_REASON,
                    source=MOVEMENT_SOURCE_ORDER,
                    reference=backfill_reference(line.order_external_id, external_product_id),
                )

    async def _describe_recipe(
        self, marketplace: str, external_product_id: str
    ) -> OfferRecipe:
        """Buduje opis jednej receptury (składniki + nazwa oferty)."""
        links = await self._inventory.get_offer_links(marketplace, external_product_id)
        names = await self._offer_names(DEFAULT_LOOKBACK_DAYS)

        described: list[RecipeComponent] = []
        for link in links:
            item = await self._inventory.get_by_sku(link.sku)
            if item is None:
                raise InventoryItemNotFoundError(link.sku)
            described.append(
                RecipeComponent(sku=item.sku, name=item.name, quantity=link.quantity)
            )

        return OfferRecipe(
            marketplace=marketplace,
            external_product_id=external_product_id,
            offer_name=names.get((marketplace, external_product_id)),
            components=tuple(described),
        )

    async def _offer_names(self, days: int) -> dict[tuple[str, str], str]:
        """Mapuje (marketplace, id oferty) na nazwę widzianą w zamówieniach."""
        since = utc_now() - timedelta(days=days)
        sold = await self._orders.get_sold_offers_since(since)
        return {(o.marketplace, o.external_product_id): o.name for o in sold}
