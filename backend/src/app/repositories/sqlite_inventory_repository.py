"""Implementacja InventoryRepository oparta o SQLAlchemy + SQLite."""

from __future__ import annotations

from datetime import datetime
from typing import cast

from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.database.models.inventory_item_model import InventoryItemModel
from app.database.models.inventory_movement_model import InventoryMovementModel
from app.database.models.offer_link_model import OfferLinkModel
from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.inventory_movement import (
    MOVEMENT_SOURCE_ORDER,
    InventoryMovement,
)
from app.domain.entities.offer_component import OfferComponent
from app.domain.exceptions.domain_exceptions import (
    DuplicateInventoryItemError,
    InventoryItemNotFoundError,
)
from app.domain.interfaces.inventory_repository import InventoryRepository
from app.shared.dto.offer_mapping_dto import OfferRecipe, RecipeComponent


class SqliteInventoryRepository(InventoryRepository):
    """Dostęp do magazynu przechowywanego w SQLite przez SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Args:
            session: Aktywna sesja SQLAlchemy, wstrzykiwana per operacja
                przez Dependency Injection.
        """
        self._session = session

    async def get_all(self) -> list[InventoryItem]:
        """Zwraca wszystkie produkty magazynowe posortowane po nazwie."""
        stmt = self._select_items().order_by(InventoryItemModel.name)
        result = await self._session.execute(stmt)
        return [self._to_domain(model, parent_sku) for model, parent_sku in result.all()]

    async def get_by_sku(self, sku: str) -> InventoryItem | None:
        """Zwraca produkt po SKU lub None, gdy nie istnieje."""
        stmt = self._select_items().where(InventoryItemModel.sku == sku)
        row = (await self._session.execute(stmt)).first()
        if row is None:
            return None
        model, parent_sku = row
        return self._to_domain(model, parent_sku)

    async def get_sub_items(self, parent_sku: str) -> list[InventoryItem]:
        """Zwraca podprodukty przypisane do danego produktu głównego."""
        parent = aliased(InventoryItemModel)
        stmt = (
            select(InventoryItemModel)
            .join(parent, InventoryItemModel.parent_item_id == parent.id)
            .where(parent.sku == parent_sku)
            .order_by(InventoryItemModel.name)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(model, parent_sku) for model in result.scalars().all()]

    async def set_parent(self, sku: str, parent_sku: str | None) -> None:
        """
        Wiąże produkt z produktem głównym albo zdejmuje to powiązanie.

        Raises:
            InventoryItemNotFoundError: Gdy `sku` albo `parent_sku` nie istnieje.
        """
        model = await self._get_model_by_sku(sku)
        if model is None:
            raise InventoryItemNotFoundError(sku)

        parent_id: int | None = None
        if parent_sku is not None:
            parent = await self._get_model_by_sku(parent_sku)
            if parent is None:
                raise InventoryItemNotFoundError(parent_sku)
            parent_id = parent.id

        model.parent_item_id = parent_id
        await self._session.flush()

    async def create(self, item: InventoryItem) -> None:
        """
        Tworzy nowy produkt magazynowy.

        Zapis odbywa się w SAVEPOINT (begin_nested), aby naruszenie
        unique constraint na SKU wycofało wyłącznie ten jeden zapis.

        Raises:
            DuplicateInventoryItemError: Gdy SKU już istnieje.
            InventoryItemNotFoundError: Gdy wskazany produkt główny nie istnieje.
        """
        parent_id: int | None = None
        if item.parent_sku is not None:
            # Dziś żadna ścieżka nie tworzy produktu od razu jako
            # podproduktu, ale encja to pole ma - ciche zgubienie go
            # przy zapisie byłoby pułapką dla następnej zmiany.
            parent = await self._get_model_by_sku(item.parent_sku)
            if parent is None:
                raise InventoryItemNotFoundError(item.parent_sku)
            parent_id = parent.id

        model = InventoryItemModel(
            sku=item.sku,
            name=item.name,
            ean=item.ean,
            category=item.category,
            stock=item.stock,
            min_stock=item.min_stock,
            max_stock=item.max_stock,
            purchase_cost=item.purchase_cost,
            sale_price=item.sale_price,
            location=item.location,
            parent_item_id=parent_id,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(model)
                await self._session.flush()
        except IntegrityError as exc:
            raise DuplicateInventoryItemError(item.sku) from exc

    async def set_stock(self, sku: str, new_stock: int) -> None:
        """Ustawia stan magazynowy produktu lub rzuca InventoryItemNotFoundError."""
        stmt = (
            update(InventoryItemModel)
            .where(InventoryItemModel.sku == sku)
            .values(stock=new_stock)
        )
        result = await self._session.execute(stmt)
        if result.rowcount == 0:
            raise InventoryItemNotFoundError(sku)
        await self._session.flush()

    async def set_min_stock(self, sku: str, min_stock: int) -> None:
        """Ustawia minimalny stan produktu lub rzuca InventoryItemNotFoundError."""
        stmt = (
            update(InventoryItemModel)
            .where(InventoryItemModel.sku == sku)
            .values(min_stock=min_stock)
        )
        result = await self._session.execute(stmt)
        if result.rowcount == 0:
            raise InventoryItemNotFoundError(sku)
        await self._session.flush()

    async def record_movement(self, movement: InventoryMovement) -> None:
        """Zapisuje ruch magazynowy powiązany z produktem po SKU."""
        model = await self._get_model_by_sku(movement.item_sku)
        if model is None:
            raise InventoryItemNotFoundError(movement.item_sku)

        self._session.add(
            InventoryMovementModel(
                item_id=model.id,
                change=movement.change,
                stock_after=movement.stock_after,
                reason=movement.reason,
                source=movement.source,
                reference=movement.reference,
                created_at=movement.occurred_at,
            )
        )
        await self._session.flush()

    async def get_movements(
        self, sku: str | None = None, limit: int = 10
    ) -> list[InventoryMovement]:
        """Zwraca ostatnie ruchy magazynowe (opcjonalnie dla jednego SKU)."""
        stmt = (
            select(InventoryMovementModel, InventoryItemModel)
            .join(
                InventoryItemModel,
                InventoryMovementModel.item_id == InventoryItemModel.id,
            )
            .order_by(
                InventoryMovementModel.created_at.desc(), InventoryMovementModel.id.desc()
            )
            .limit(limit)
        )
        if sku is not None:
            stmt = stmt.where(InventoryItemModel.sku == sku)

        result = await self._session.execute(stmt)
        return [
            InventoryMovement(
                item_sku=item.sku,
                item_name=item.name,
                change=movement.change,
                stock_after=movement.stock_after,
                reason=movement.reason,
                source=movement.source,
                reference=movement.reference,
                occurred_at=movement.created_at,
            )
            for movement, item in result.all()
        ]

    async def get_low_stock(self) -> list[InventoryItem]:
        """
        Zwraca produkty, które osiągnęły minimalny stan magazynowy.

        Podprodukty są tu równoprawne z produktami głównymi - kończące
        się nakrętki trzeba dokupić tak samo jak butelki, mimo że lista
        magazynowa chowa je pod produktem głównym.
        """
        stmt = (
            self._select_items()
            .where(
                InventoryItemModel.min_stock > 0,
                InventoryItemModel.stock <= InventoryItemModel.min_stock,
            )
            .order_by(InventoryItemModel.name)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(model, parent_sku) for model, parent_sku in result.all()]

    async def get_sales_since(self, since: datetime) -> dict[str, int]:
        """Sumuje sprzedane sztuki (ruchy o źródle 'order') od podanej daty."""
        stmt = (
            select(InventoryItemModel.sku, func.sum(-InventoryMovementModel.change))
            .join(
                InventoryItemModel,
                InventoryMovementModel.item_id == InventoryItemModel.id,
            )
            .where(
                InventoryMovementModel.source == MOVEMENT_SOURCE_ORDER,
                InventoryMovementModel.change < 0,
                InventoryMovementModel.created_at >= since,
            )
            .group_by(InventoryItemModel.sku)
        )
        result = await self._session.execute(stmt)
        return {sku: int(total) for sku, total in result.all()}

    async def get_offer_links(
        self, marketplace: str, external_product_id: str
    ) -> list[OfferComponent]:
        """Zwraca składniki magazynowe przypisane do oferty marketplace."""
        stmt = (
            select(InventoryItemModel.sku, OfferLinkModel.quantity)
            .join(InventoryItemModel, OfferLinkModel.item_id == InventoryItemModel.id)
            .where(
                OfferLinkModel.marketplace == marketplace,
                OfferLinkModel.external_product_id == external_product_id,
            )
        )
        result = await self._session.execute(stmt)
        return [OfferComponent(sku=sku, quantity=quantity) for sku, quantity in result.all()]

    async def add_offer_link(
        self, marketplace: str, external_product_id: str, sku: str, quantity: int
    ) -> None:
        """
        Przypisuje produkt magazynowy jako składnik oferty marketplace.

        Ponowne przypisanie tego samego SKU do tej samej oferty nadpisuje
        ilość zamiast dokładać drugi wiersz - inaczej poprawka literówki
        w `/stock link` cicho podwajałaby odejmowanie przy każdej sprzedaży.
        """
        model = await self._get_model_by_sku(sku)
        if model is None:
            raise InventoryItemNotFoundError(sku)

        existing = await self._session.execute(
            select(OfferLinkModel).where(
                OfferLinkModel.marketplace == marketplace,
                OfferLinkModel.external_product_id == external_product_id,
                OfferLinkModel.item_id == model.id,
            )
        )
        link = existing.scalar_one_or_none()
        if link is not None:
            link.quantity = quantity
        else:
            self._session.add(
                OfferLinkModel(
                    marketplace=marketplace,
                    external_product_id=external_product_id,
                    item_id=model.id,
                    quantity=quantity,
                )
            )
        await self._session.flush()

    async def get_all_offer_links(self) -> list[OfferRecipe]:
        """Zwraca wszystkie receptury ofert pogrupowane po ofercie."""
        stmt = (
            select(
                OfferLinkModel.marketplace,
                OfferLinkModel.external_product_id,
                InventoryItemModel.sku,
                InventoryItemModel.name,
                OfferLinkModel.quantity,
            )
            .join(InventoryItemModel, OfferLinkModel.item_id == InventoryItemModel.id)
            .order_by(OfferLinkModel.external_product_id, InventoryItemModel.name)
        )
        result = await self._session.execute(stmt)

        grouped: dict[tuple[str, str], list[RecipeComponent]] = {}
        for marketplace, external_product_id, sku, name, quantity in result.all():
            grouped.setdefault((marketplace, external_product_id), []).append(
                RecipeComponent(sku=sku, name=name, quantity=quantity)
            )

        return [
            OfferRecipe(
                marketplace=marketplace,
                external_product_id=external_product_id,
                offer_name=None,
                components=tuple(components),
            )
            for (marketplace, external_product_id), components in grouped.items()
        ]

    async def replace_offer_links(
        self, marketplace: str, external_product_id: str, components: list[OfferComponent]
    ) -> None:
        """
        Zastępuje całą recepturę oferty podaną listą składników.

        Raises:
            InventoryItemNotFoundError: Gdy któreś SKU nie istnieje.
        """
        models = []
        for component in components:
            model = await self._get_model_by_sku(component.sku)
            if model is None:
                raise InventoryItemNotFoundError(component.sku)
            models.append((model.id, component.quantity))

        await self.remove_offer_links(marketplace, external_product_id)
        for item_id, quantity in models:
            self._session.add(
                OfferLinkModel(
                    marketplace=marketplace,
                    external_product_id=external_product_id,
                    item_id=item_id,
                    quantity=quantity,
                )
            )
        await self._session.flush()

    async def get_movement_references(self, sku: str) -> set[str]:
        """
        Zwraca numery dokumentów (zamówień, zwrotów), dla których produkt
        ma już zapisany ruch magazynowy.

        Korekta wsteczna używa tego zbioru, żeby nie odjąć drugi raz
        zamówienia, które kiedyś zostało rozliczone poprawnie.
        """
        stmt = (
            select(InventoryMovementModel.reference)
            .join(
                InventoryItemModel,
                InventoryMovementModel.item_id == InventoryItemModel.id,
            )
            .where(
                InventoryItemModel.sku == sku,
                InventoryMovementModel.reference.is_not(None),
            )
            .distinct()
        )
        result = await self._session.execute(stmt)
        return {reference for (reference,) in result.all() if reference}

    async def remove_offer_links(self, marketplace: str, external_product_id: str) -> int:
        """Usuwa wszystkie składniki oferty. Zwraca liczbę usuniętych wpisów."""
        stmt = delete(OfferLinkModel).where(
            OfferLinkModel.marketplace == marketplace,
            OfferLinkModel.external_product_id == external_product_id,
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount or 0

    async def _get_model_by_sku(self, sku: str) -> InventoryItemModel | None:
        """Zwraca model ORM produktu po SKU lub None."""
        stmt = select(InventoryItemModel).where(InventoryItemModel.sku == sku)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def _select_items() -> Select[tuple[InventoryItemModel, str | None]]:
        """
        Zapytanie o produkty wraz z SKU produktu głównego.

        LEFT JOIN po tej samej tabeli, bo encja domenowa mówi
        `parent_sku`, a w bazie leży `parent_item_id`. Bez tego joinu
        każdy odczyt listy musiałby dociągać rodzica osobnym zapytaniem
        na wiersz.
        """
        parent = aliased(InventoryItemModel)
        # `cast` zamiast wnioskowania: kolumna `sku` jest NOT NULL, więc
        # SQLAlchemy typuje ją jako `str` - ale LEFT JOIN zwraca dla niej
        # NULL przy każdym produkcie bez produktu głównego. Prawdą jest
        # typ z adnotacji, nie ten z modelu.
        return cast(
            "Select[tuple[InventoryItemModel, str | None]]",
            select(InventoryItemModel, parent.sku).outerjoin(
                parent, InventoryItemModel.parent_item_id == parent.id
            ),
        )

    @staticmethod
    def _to_domain(model: InventoryItemModel, parent_sku: str | None = None) -> InventoryItem:
        """Mapuje model ORM na encję domenową InventoryItem."""
        return InventoryItem(
            sku=model.sku,
            name=model.name,
            stock=model.stock,
            min_stock=model.min_stock,
            ean=model.ean,
            category=model.category,
            max_stock=model.max_stock,
            purchase_cost=model.purchase_cost,
            sale_price=model.sale_price,
            location=model.location,
            parent_sku=parent_sku,
        )
