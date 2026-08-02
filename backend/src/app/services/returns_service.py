"""Logika aplikacyjna dla odczytu zwrotów klientów (GET /api/v1/returns)."""

from __future__ import annotations

from app.domain.entities.order_return import ReturnRecord
from app.domain.interfaces.return_repository import ReturnRepository


class ReturnsService:
    """Cienka warstwa nad ReturnRepository - dziś tylko odczyt do wyświetlenia."""

    def __init__(self, return_repository: ReturnRepository) -> None:
        self._return_repository = return_repository

    async def get_recent_returns(self, limit: int = 50, offset: int = 0) -> list[ReturnRecord]:
        """Zwraca ostatnie zwroty, najnowsze pierwsze."""
        return await self._return_repository.get_recent(limit=limit, offset=offset)
