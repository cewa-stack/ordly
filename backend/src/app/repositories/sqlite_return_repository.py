"""Implementacja ReturnRepository oparta o SQLAlchemy + SQLite."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.order_model import OrderModel
from app.database.models.return_model import ReturnModel
from app.domain.entities.order_return import OrderReturn, ReturnRecord
from app.domain.exceptions.domain_exceptions import DuplicateReturnError
from app.domain.interfaces.return_repository import ReturnRepository
from app.domain.returns import CLOSED_RETURN_STATUSES


class SqliteReturnRepository(ReturnRepository):
    """Dostęp do zwrotów przechowywanych w SQLite przez SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Args:
            session: Aktywna sesja SQLAlchemy, wstrzykiwana per operacja
                przez Dependency Injection.
        """
        self._session = session

    async def exists(self, marketplace: str, external_id: str) -> bool:
        """Sprawdza istnienie zwrotu przez zapytanie COUNT zamiast pełnego SELECT."""
        stmt = (
            select(func.count())
            .select_from(ReturnModel)
            .where(
                ReturnModel.marketplace == marketplace,
                ReturnModel.external_id == external_id,
            )
        )
        result = await self._session.execute(stmt)
        return (result.scalar_one() or 0) > 0

    async def save(self, order_return: OrderReturn) -> None:
        """
        Zapisuje zwrot klienta.

        Zapis odbywa się w SAVEPOINT (begin_nested), aby naruszenie
        unique constraint (marketplace, external_id) wycofało wyłącznie
        ten jeden zwrot - a nie całą transakcję synchronizacji.

        Raises:
            DuplicateReturnError: Gdy zwrot już istnieje w bazie.
        """
        model = ReturnModel(
            marketplace=order_return.marketplace,
            external_id=order_return.external_id,
            order_external_id=order_return.order_external_id,
            buyer_login=order_return.buyer_login,
            status=order_return.status,
            products_summary=order_return.products_summary,
            return_date=order_return.created_at,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(model)
                await self._session.flush()
        except IntegrityError as exc:
            raise DuplicateReturnError(
                order_return.marketplace, order_return.external_id
            ) from exc

    async def get_recent(self, limit: int = 50, offset: int = 0) -> list[ReturnRecord]:
        """Zwraca ostatnie zwroty posortowane malejąco po dacie zwrotu."""
        stmt = (
            self._select_with_order_status()
            .order_by(ReturnModel.return_date.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [self._to_record(model, order_status) for model, order_status in result.all()]

    async def get_status(self, marketplace: str, external_id: str) -> str | None:
        stmt = select(ReturnModel.status).where(
            ReturnModel.marketplace == marketplace,
            ReturnModel.external_id == external_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(self, marketplace: str, external_id: str, status: str) -> None:
        stmt = (
            update(ReturnModel)
            .where(
                ReturnModel.marketplace == marketplace,
                ReturnModel.external_id == external_id,
            )
            .values(status=status)
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_open(self, marketplace: str, limit: int) -> list[ReturnRecord]:
        stmt = (
            self._select_with_order_status()
            .where(
                ReturnModel.marketplace == marketplace,
                func.upper(ReturnModel.status).not_in(list(CLOSED_RETURN_STATUSES)),
            )
            .order_by(ReturnModel.return_date.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_record(model, order_status) for model, order_status in result.all()]

    @staticmethod
    def _select_with_order_status() -> Any:
        """Zwrot + status zamówienia, którego dotyczy (lewe złączenie)."""
        return select(ReturnModel, OrderModel.status).outerjoin(
            OrderModel,
            (OrderModel.marketplace == ReturnModel.marketplace)
            & (OrderModel.external_id == ReturnModel.order_external_id),
        )

    @staticmethod
    def _to_record(model: ReturnModel, order_status: str | None) -> ReturnRecord:
        return ReturnRecord(
            external_id=model.external_id,
            marketplace=model.marketplace,
            order_external_id=model.order_external_id,
            buyer_login=model.buyer_login,
            status=model.status,
            products_summary=model.products_summary,
            return_date=model.return_date,
            order_status=order_status,
        )
