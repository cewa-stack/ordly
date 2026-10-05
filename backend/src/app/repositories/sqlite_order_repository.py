"""Implementacja OrderRepository oparta o SQLAlchemy + SQLite."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ColumnElement, and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models.order_model import OrderModel
from app.database.models.order_status_change_model import OrderStatusChangeModel
from app.database.models.product_model import ProductModel
from app.database.models.shipment_model import ShipmentModel
from app.domain.entities.customer import Customer
from app.domain.entities.order import Order
from app.domain.entities.product import Product
from app.domain.exceptions.domain_exceptions import DuplicateOrderError
from app.domain.fulfillment import (
    AWAITING_SHIPMENT_FULFILLMENT_STATUSES,
    FULFILLMENT_NEW,
    PACKING_FULFILLMENT_STATUSES,
    REFRESHABLE_FULFILLMENT_STATUSES,
)
from app.domain.interfaces.order_repository import OrderRepository
from app.domain.order_status import (
    OPEN_APP_STATUSES,
    OrderStatusChange,
    order_awaits_shipment,
    order_needs_new_reminder,
    order_requires_packing,
)
from app.utils.time import utc_now

_CANCELLED_STATUS = "CANCELLED"


def _open_without_waybill(fulfillment_statuses: frozenset[str]) -> ColumnElement[bool]:
    """
    Lustro SQL reguł `requires_packing` / `awaits_shipment` z
    app/domain/fulfillment.py: nieanulowane, bez numeru przesyłki, z etapem
    z podanego zbioru (NULL do żadnego zbioru nie należy). Zapytanie musi
    mieć lewe złączenie z `shipments`. Zgodność z regułą w Pythonie pilnuje
    test tests/integration/repositories/test_order_rules_parity.py.
    """
    return and_(
        func.upper(OrderModel.status) != _CANCELLED_STATUS,
        func.upper(OrderModel.fulfillment_status).in_(list(fulfillment_statuses)),
        ShipmentModel.tracking_number.is_(None),
    )


def _or_manually_open(rule: ColumnElement[bool]) -> ColumnElement[bool]:
    """
    Kandydaci do reguł z uwzględnieniem statusu aplikacyjnego
    (app/domain/order_status.py): dotychczasowa reguła SQL ALBO zamówienie
    ręcznie oznaczone jako Nowe / W realizacji. Ostateczną decyzję podejmuje
    reguła domenowa w Pythonie - ręcznie zamknięte zamówienia odpadają tam,
    a SQL tylko zawęża zbiór, żeby nie czytać całej tabeli.
    """
    return or_(rule, OrderModel.app_status.in_(list(OPEN_APP_STATUSES)))


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
        stmt = (
            select(func.count())
            .select_from(OrderModel)
            .where(
                OrderModel.marketplace == marketplace,
                OrderModel.external_id == external_id,
            )
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
            .options(selectinload(OrderModel.products), selectinload(OrderModel.shipment))
            .where(OrderModel.external_id == external_id)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_recent(self, limit: int, offset: int = 0) -> list[Order]:
        """Zwraca ostatnie zamówienia posortowane malejąco po dacie zamówienia."""
        stmt = (
            select(OrderModel)
            .options(selectinload(OrderModel.products), selectinload(OrderModel.shipment))
            .order_by(OrderModel.order_date.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def get_unshipped_since(self, since: datetime) -> list[Order]:
        """
        Zwraca niewysłane zamówienia utworzone od podanej daty.

        Niewysłane = reguła `awaits_shipment` (etap NEW / PROCESSING /
        READY_FOR_SHIPMENT, bez numeru przesyłki, nieanulowane). Wcześniej
        liczyło się tu wszystko poza SENT/PICKED_UP - także zamówienia
        zwrócone, wstrzymane, do odbioru osobistego i z etapem NULL, które
        nabijały kafel "Do wysyłki".
        """
        stmt = (
            select(OrderModel)
            .options(selectinload(OrderModel.products), selectinload(OrderModel.shipment))
            .outerjoin(ShipmentModel, ShipmentModel.order_id == OrderModel.id)
            .where(
                OrderModel.order_date >= since,
                _open_without_waybill(AWAITING_SHIPMENT_FULFILLMENT_STATUSES),
            )
            .order_by(OrderModel.order_date.desc())
        )
        result = await self._session.execute(stmt)
        orders = [self._to_domain(m) for m in result.scalars().all()]
        # Ręcznie zamknięte w aplikacji (Zrealizowane / Anulowane) odpadają.
        return [order for order in orders if order_awaits_shipment(order)]

    async def get_new_status(self) -> list[Order]:
        """
        Zwraca wszystkie zamówienia o statusie realizacji dokładnie "NEW",
        niezależnie od daty, pomijając anulowane.

        NULL (etap realizacji nigdy nie pobrany z marketplace) NIE liczy
        się jako NEW - patrz uzasadnienie w OrderRepository.get_new_status.
        """
        stmt = (
            select(OrderModel)
            .options(selectinload(OrderModel.products), selectinload(OrderModel.shipment))
            .outerjoin(ShipmentModel, ShipmentModel.order_id == OrderModel.id)
            .where(
                # Podzbiór `requires_packing`: tylko nietknięte (NEW).
                # Wykryty numer przesyłki = paczka nadana, nawet gdy
                # Allegro zostawiło etap NEW - tak samo jak w aplikacjach.
                _or_manually_open(
                    and_(
                        _open_without_waybill(PACKING_FULFILLMENT_STATUSES),
                        func.upper(OrderModel.fulfillment_status) == FULFILLMENT_NEW,
                    )
                ),
            )
            .order_by(OrderModel.order_date.desc())
        )
        result = await self._session.execute(stmt)
        orders = [self._to_domain(m) for m in result.scalars().all()]
        return [order for order in orders if order_needs_new_reminder(order)]

    async def get_active(self, limit: int) -> list[Order]:
        """
        Zwraca aktywne zamówienia (nowe lub pakowane), od najnowszego.

        Filtr po statusie realizacji NEW/PROCESSING automatycznie pomija
        zamówienia wysłane, anulowane oraz te bez znanego etapu realizacji
        (fulfillment_status NULL nie należy do zbioru aktywnych).
        """
        stmt = (
            select(OrderModel)
            .options(selectinload(OrderModel.products), selectinload(OrderModel.shipment))
            .outerjoin(ShipmentModel, ShipmentModel.order_id == OrderModel.id)
            .where(_or_manually_open(_open_without_waybill(PACKING_FULFILLMENT_STATUSES)))
            .order_by(OrderModel.order_date.desc())
        )
        result = await self._session.execute(stmt)
        orders = [self._to_domain(m) for m in result.scalars().all()]
        # Limit PO regule domenowej - inaczej ręcznie zamknięte zamówienia
        # zajmowałyby miejsca w limicie i wypychały aktywne.
        return [order for order in orders if order_requires_packing(order)][:limit]

    async def get_open_for_refresh(self, marketplace: str, limit: int) -> list[Order]:
        """Zamówienia do potwierdzenia u źródła - patrz OrderRepository."""
        stmt = (
            select(OrderModel)
            .options(selectinload(OrderModel.products), selectinload(OrderModel.shipment))
            .outerjoin(ShipmentModel, ShipmentModel.order_id == OrderModel.id)
            .where(
                OrderModel.marketplace == marketplace,
                func.upper(OrderModel.status) != _CANCELLED_STATUS,
                or_(
                    OrderModel.fulfillment_status.is_(None),
                    func.upper(OrderModel.fulfillment_status).in_(
                        list(REFRESHABLE_FULFILLMENT_STATUSES)
                    ),
                ),
                ShipmentModel.tracking_number.is_(None),
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
            .options(selectinload(OrderModel.products), selectinload(OrderModel.shipment))
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
        """Liczy zamówienia utworzone od podanej daty, bez anulowanych."""
        stmt = (
            select(func.count())
            .select_from(OrderModel)
            .where(
                OrderModel.order_date >= since,
                func.upper(OrderModel.status) != _CANCELLED_STATUS,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one() or 0

    async def sum_amount_since(self, since: datetime) -> float:
        """
        Sumuje kwoty zamówień od podanej daty, bez anulowanych.

        Anulowane zamówienie nie przyniosło pieniędzy - wcześniej wliczało
        się do "Przychodu dziś" i statystyk miesiąca na równi ze sprzedażą.
        """
        stmt = select(func.coalesce(func.sum(OrderModel.total_amount), 0)).where(
            OrderModel.order_date >= since,
            func.upper(OrderModel.status) != _CANCELLED_STATUS,
        )
        result = await self._session.execute(stmt)
        return float(result.scalar_one())

    async def count_all(self) -> int:
        """Zwraca łączną liczbę zamówień w bazie."""
        stmt = select(func.count()).select_from(OrderModel)
        result = await self._session.execute(stmt)
        return result.scalar_one() or 0

    async def sum_amount_by_day(self, since: datetime) -> dict[str, float]:
        """
        Sumuje kwoty zamówień pogrupowane po dniu UTC (`func.date` - SQLite),
        bez anulowanych.

        Doby są tu UTC - ekrany i asystent liczą przychód dzienny w polskich
        dobach przez `revenue_by_local_day`, nie przez tę metodę.
        """
        day = func.date(OrderModel.order_date)
        stmt = (
            select(day, func.coalesce(func.sum(OrderModel.total_amount), 0))
            .where(
                OrderModel.order_date >= since,
                func.upper(OrderModel.status) != _CANCELLED_STATUS,
            )
            .group_by(day)
        )
        result = await self._session.execute(stmt)
        return {str(row[0]): float(row[1]) for row in result.all()}

    async def get_between(self, start: datetime, end: datetime) -> list[Order]:
        """
        Zamówienia z przedziału [start, end) od najnowszego, razem z
        anulowanymi (historia na Control Hubie pokazuje je wyszarzone).
        """
        stmt = (
            select(OrderModel)
            .options(selectinload(OrderModel.products), selectinload(OrderModel.shipment))
            .where(OrderModel.order_date >= start, OrderModel.order_date < end)
            .order_by(OrderModel.order_date.desc(), OrderModel.id.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def latest_order_date_before(self, before: datetime) -> datetime | None:
        """Data najnowszego zamówienia sprzed podanej chwili (None, gdy nie ma)."""
        stmt = select(func.max(OrderModel.order_date)).where(OrderModel.order_date < before)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def earliest_order_date_since(self, since: datetime) -> datetime | None:
        """Data najstarszego zamówienia od podanej chwili (None, gdy nie ma)."""
        stmt = select(func.min(OrderModel.order_date)).where(OrderModel.order_date >= since)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(self, marketplace: str, external_id: str, status: str) -> None:
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

    async def set_app_status(
        self,
        marketplace: str,
        external_id: str,
        app_status: str | None,
        basis: str | None,
        changed_at: datetime | None,
    ) -> None:
        """Zapisuje ręczny status aplikacyjny (None = powrót do statusu z Allegro)."""
        stmt = (
            update(OrderModel)
            .where(
                OrderModel.marketplace == marketplace,
                OrderModel.external_id == external_id,
            )
            .values(
                app_status=app_status,
                app_status_basis=basis,
                app_status_changed_at=changed_at,
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def record_app_status_change(self, change: OrderStatusChange) -> None:
        """Dopisuje wpis do historii zmian statusu aplikacyjnego."""
        self._session.add(
            OrderStatusChangeModel(
                marketplace=change.marketplace,
                order_external_id=change.order_external_id,
                previous_status=change.previous_status,
                new_status=change.new_status,
                source=change.source,
                changed_at=change.changed_at,
            )
        )
        await self._session.flush()

    async def get_app_status_history(self, external_id: str) -> list[OrderStatusChange]:
        """Historia zmian statusu aplikacyjnego zamówienia, od najnowszej."""
        stmt = (
            select(OrderStatusChangeModel)
            .where(OrderStatusChangeModel.order_external_id == external_id)
            .order_by(
                OrderStatusChangeModel.changed_at.desc(), OrderStatusChangeModel.id.desc()
            )
        )
        result = await self._session.execute(stmt)
        return [
            OrderStatusChange(
                marketplace=m.marketplace,
                order_external_id=m.order_external_id,
                previous_status=m.previous_status,
                new_status=m.new_status,
                source=m.source,
                changed_at=m.changed_at,
            )
            for m in result.scalars().all()
        ]

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
            tracking_number=model.shipment.tracking_number if model.shipment else None,
            app_status=model.app_status,
            app_status_basis=model.app_status_basis,
            app_status_changed_at=model.app_status_changed_at,
        )
