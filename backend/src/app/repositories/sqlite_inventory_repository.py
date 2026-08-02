"""Implementacja InventoryRepository oparta o SQLAlchemy + SQLite."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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
        stmt = select(InventoryItemModel).order_by(InventoryItemModel.name)
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def get_by_sku(self, sku: str) -> InventoryItem | None:
        """Zwraca produkt po SKU lub None, gdy nie istnieje."""
        model = await self._get_model_by_sku(sku)
        return self._to_domain(model) if model else None

    async def create(self, item: InventoryItem) -> None:
        """
        Tworzy nowy produkt magazynowy.

        Zapis odbywa się w SAVEPOINT (begin_nested), aby naruszenie
        unique constraint na SKU wycofało wyłącznie ten jeden zapis.

        Raises:
            DuplicateInventoryItemError: Gdy SKU już istnieje.
        """
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
        """Zwraca produkty, które osiągnęły minimalny stan magazynowy."""
        stmt = (
            select(InventoryItemModel)
            .where(
                InventoryItemModel.min_stock > 0,
                InventoryItemModel.stock <= InventoryItemModel.min_stock,
            )
            .order_by(InventoryItemModel.name)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

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
        """Przypisuje produkt magazynowy jako składnik oferty marketplace."""
        model = await self._get_model_by_sku(sku)
        if model is None:
            raise InventoryItemNotFoundError(sku)

        self._session.add(
            OfferLinkModel(
                marketplace=marketplace,
                external_product_id=external_product_id,
                item_id=model.id,
                quantity=quantity,
            )
        )
        await self._session.flush()

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
    def _to_domain(model: InventoryItemModel) -> InventoryItem:
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
        )
