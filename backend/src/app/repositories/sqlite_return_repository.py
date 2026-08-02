"""Implementacja ReturnRepository oparta o SQLAlchemy + SQLite."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.return_model import ReturnModel
from app.domain.entities.order_return import OrderReturn, ReturnRecord
from app.domain.exceptions.domain_exceptions import DuplicateReturnError
from app.domain.interfaces.return_repository import ReturnRepository


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
            select(ReturnModel)
            .order_by(ReturnModel.return_date.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [
            ReturnRecord(
                external_id=m.external_id,
                marketplace=m.marketplace,
                order_external_id=m.order_external_id,
                buyer_login=m.buyer_login,
                status=m.status,
                products_summary=m.products_summary,
                return_date=m.return_date,
            )
            for m in result.scalars().all()
        ]
