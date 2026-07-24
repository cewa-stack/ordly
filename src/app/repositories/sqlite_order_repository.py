"""Implementacja OrderRepository oparta o SQLAlchemy + SQLite."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models.order_model import OrderModel
from app.database.models.product_model import ProductModel
from app.database.models.shipment_model import ShipmentModel
from app.domain.entities.customer import Customer
from app.domain.entities.order import Order
from app.domain.entities.product import Product
from app.domain.exceptions.domain_exceptions import DuplicateOrderError
from app.domain.fulfillment import (
    ACTIVE_FULFILLMENT_STATUSES,
    SHIPPED_FULFILLMENT_STATUSES,
)
from app.domain.interfaces.order_repository import OrderRepository
from app.utils.time import utc_now

_CANCELLED_STATUS = "CANCELLED"


class SqliteOrderRepository(OrderRepository):
    """Dostęp do zamówień przechowywanych w SQLite przez SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Args:
            session: Aktywna sesja SQLAlchemy, wstrzykiwana per operacja
                przez Dependency Injection.
        """
        self._session = session

    async def exists(self, marketplace: str, external_id: str) -> bool:
        """Sprawdza istnienie zamówienia przez zapytanie COUNT zamiast pełnego SELECT."""
        stmt = select(func.count()).select_from(OrderModel).where(
            OrderModel.marketplace == marketplace,
            OrderModel.external_id == external_id,
        )
        result = await self._session.execute(stmt)
        return (result.scalar_one() or 0) > 0

    async def save(self, order: Order) -> None:
        """
        Zapisuje zamówienie wraz z produktami.

        Zapis odbywa się w SAVEPOINT (begin_nested), aby naruszenie
        unique constraint (marketplace, external_id) wycofało wyłącznie
        to jedno zamówienie - a nie całą transakcję z wcześniej
        zapisanymi zamówieniami z tej samej partii synchronizacji.

        Raises:
            DuplicateOrderError: Gdy zamówienie już istnieje w bazie.
        """
        model = OrderModel(
            marketplace=order.marketplace,
            external_id=order.external_id,
            buyer_login=order.buyer.login,
            buyer_email=order.buyer.email,
            buyer_phone=order.buyer.phone_number,
            total_amount=order.total_amount,
            currency=order.currency,
            status=order.status,
            fulfillment_status=order.fulfillment_status,
            order_date=order.order_date,
            raw_payload_json=None,
            products=[
                ProductModel(
                    external_product_id=p.external_id,
                    name=p.name,
                    quantity=p.quantity,
                    unit_price=p.unit_price,
                )
                for p in order.products
            ],
        )
        try:
            async with self._session.begin_nested():
                self._session.add(model)
                await self._session.flush()
        except IntegrityError as exc:
            raise DuplicateOrderError(order.marketplace, order.external_id) from exc

    async def get_by_external_id(self, external_id: str) -> Order | None:
        """Zwraca zamówienie wraz z produktami, mapowane do encji domenowej."""
        stmt = (
            select(OrderModel)
            .options(selectinload(OrderModel.products))
            .where(OrderModel.external_id == external_id)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_recent(self, limit: int, offset: int = 0) -> list[Order]:
        """Zwraca ostatnie zamówienia posortowane malejąco po dacie zamówienia."""
        stmt = (
            select(OrderModel)
            .options(selectinload(OrderModel.products))
            .order_by(OrderModel.order_date.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def get_unshipped_since(self, since: datetime) -> list[Order]:
        """
        Zwraca niewysłane zamówienia utworzone od podanej daty.

        Niewysłane = status realizacji nie jest SENT/PICKED_UP ORAZ brak
        zapisanego numeru przewozowego. Zamówienia anulowane są pomijane.
        Lewe złączenie z shipments pozwala wykryć numer przewozowy zapisany
        wcześniej komendą /tracking (jedna przesyłka na zamówienie).
        """
        stmt = (
            select(OrderModel)
            .options(selectinload(OrderModel.products))
            .outerjoin(ShipmentModel, ShipmentModel.order_id == OrderModel.id)
            .where(
                OrderModel.order_date >= since,
                func.upper(OrderModel.status) != _CANCELLED_STATUS,
                or_(
                    OrderModel.fulfillment_status.is_(None),
                    func.upper(OrderModel.fulfillment_status).not_in(
                        list(SHIPPED_FULFILLMENT_STATUSES)
                    ),
                ),
                ShipmentModel.tracking_number.is_(None),
            )
            .order_by(OrderModel.order_date.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def get_active(self, limit: int) -> list[Order]:
        """
        Zwraca aktywne zamówienia (nowe lub pakowane), od najnowszego.

        Filtr po statusie realizacji NEW/PROCESSING automatycznie pomija
        zamówienia wysłane, anulowane oraz te bez znanego etapu realizacji
        (fulfillment_status NULL nie należy do zbioru aktywnych).
        """
        stmt = (
            select(OrderModel)
            .options(selectinload(OrderModel.products))
            .where(
                func.upper(OrderModel.status) != _CANCELLED_STATUS,
                func.upper(OrderModel.fulfillment_status).in_(
                    list(ACTIVE_FULFILLMENT_STATUSES)
                ),
            )
            .order_by(OrderModel.order_date.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def search(self, query: str) -> list[Order]:
        """Wyszukuje zamówienia po numerze, loginie kupującego lub nazwie produktu."""
        pattern = f"%{query}%"
        stmt = (
            select(OrderModel)
            .options(selectinload(OrderModel.products))
            .join(ProductModel, isouter=True)
            .where(
                or_(
                    OrderModel.external_id.ilike(pattern),
                    OrderModel.buyer_login.ilike(pattern),
                    ProductModel.name.ilike(pattern),
                )
            )
            .distinct()
            .order_by(OrderModel.order_date.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def count_since(self, since: datetime) -> int:
        """Liczy zamówienia utworzone od podanej daty."""
        stmt = select(func.count()).select_from(OrderModel).where(
            OrderModel.order_date >= since
        )
        result = await self._session.execute(stmt)
        return result.scalar_one() or 0

    async def sum_amount_since(self, since: datetime) -> float:
        """Sumuje kwoty zamówień od podanej daty."""
        stmt = select(func.coalesce(func.sum(OrderModel.total_amount), 0)).where(
            OrderModel.order_date >= since
        )
        result = await self._session.execute(stmt)
        return float(result.scalar_one())

    async def count_all(self) -> int:
        """Zwraca łączną liczbę zamówień w bazie."""
        stmt = select(func.count()).select_from(OrderModel)
        result = await self._session.execute(stmt)
        return result.scalar_one() or 0

    async def sum_amount_by_day(self, since: datetime) -> dict[str, float]:
        """Sumuje kwoty zamówień pogrupowane po dniu (`func.date` - SQLite)."""
        day = func.date(OrderModel.order_date)
        stmt = (
            select(day, func.coalesce(func.sum(OrderModel.total_amount), 0))
            .where(OrderModel.order_date >= since)
            .group_by(day)
        )
        result = await self._session.execute(stmt)
        return {str(row[0]): float(row[1]) for row in result.all()}

    async def update_status(
        self, marketplace: str, external_id: str, status: str
    ) -> None:
        """Aktualizuje status zamówienia wykryty podczas synchronizacji."""
        stmt = (
            update(OrderModel)
            .where(
                OrderModel.marketplace == marketplace,
                OrderModel.external_id == external_id,
            )
            .values(status=status)
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def update_fulfillment_status(
        self, marketplace: str, external_id: str, fulfillment_status: str | None
    ) -> None:
        """Aktualizuje etap realizacji zamówienia wykryty podczas synchronizacji."""
        stmt = (
            update(OrderModel)
            .where(
                OrderModel.marketplace == marketplace,
                OrderModel.external_id == external_id,
            )
            .values(fulfillment_status=fulfillment_status)
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def mark_as_notified(self, marketplace: str, external_id: str) -> None:
        """Ustawia znacznik czasu wysłania powiadomienia dla danego zamówienia."""
        stmt = (
            update(OrderModel)
            .where(
                OrderModel.marketplace == marketplace,
                OrderModel.external_id == external_id,
            )
            .values(notified_at=utc_now())
        )
        await self._session.execute(stmt)
        await self._session.flush()

    @staticmethod
    def _to_domain(model: OrderModel) -> Order:
        """Mapuje model ORM na encję domenową Order."""
        return Order(
            external_id=model.external_id,
            marketplace=model.marketplace,
            buyer=Customer(
                login=model.buyer_login,
                email=model.buyer_email,
                phone_number=model.buyer_phone,
            ),
            products=[
                Product(
                    external_id=p.external_product_id,
                    name=p.name,
                    quantity=p.quantity,
                    unit_price=p.unit_price,
                )
                for p in model.products
            ],
            total_amount=model.total_amount,
            currency=model.currency,
            status=model.status,
            order_date=model.order_date,
            fulfillment_status=model.fulfillment_status,
        )
