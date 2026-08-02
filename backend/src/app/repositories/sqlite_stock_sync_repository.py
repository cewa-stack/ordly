"""Implementacja StockSyncRepository oparta o SQLAlchemy + SQLite."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.stock_sync_model import StockSyncModel
from app.domain.interfaces.stock_sync_repository import StockSyncRepository


class SqliteStockSyncRepository(StockSyncRepository):
    """Rejestr przetworzonych operacji magazynowych w SQLite."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Args:
            session: Aktywna sesja SQLAlchemy, wstrzykiwana per operacja
                przez Dependency Injection.
        """
        self._session = session

    async def was_processed(self, marketplace: str, reference: str, operation: str) -> bool:
        """Sprawdza istnienie znacznika przez zapytanie COUNT."""
        stmt = (
            select(func.count())
            .select_from(StockSyncModel)
            .where(
                StockSyncModel.marketplace == marketplace,
                StockSyncModel.reference == reference,
                StockSyncModel.operation == operation,
            )
        )
        result = await self._session.execute(stmt)
        return (result.scalar_one() or 0) > 0

    async def mark_processed(self, marketplace: str, reference: str, operation: str) -> bool:
        """
        Rejestruje wykonanie operacji w SAVEPOINT (begin_nested).

        Naruszenie unique constraint (operacja już zarejestrowana,
        np. przez równoległą synchronizację) zwraca False zamiast
        wycofywać całą transakcję.
        """
        model = StockSyncModel(
            marketplace=marketplace, reference=reference, operation=operation
        )
        try:
            async with self._session.begin_nested():
                self._session.add(model)
                await self._session.flush()
        except IntegrityError:
            return False
        return True
