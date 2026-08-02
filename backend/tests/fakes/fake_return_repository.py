"""Fake implementacja ReturnRepository - działa w pamięci, bez bazy danych."""

from __future__ import annotations

from app.domain.entities.order_return import OrderReturn, ReturnRecord
from app.domain.interfaces.return_repository import ReturnRepository


class FakeReturnRepository(ReturnRepository):
    """
    Implementacja ReturnRepository trzymająca dane w zwykłej liście Pythona.

    Używana w testach jednostkowych serwisów, żeby nie zależeć od
    prawdziwej bazy danych.
    """

    def __init__(self) -> None:
        self._returns: list[OrderReturn] = []

    async def exists(self, marketplace: str, external_id: str) -> bool:
        return any(
            r.marketplace == marketplace and r.external_id == external_id
            for r in self._returns
        )

    async def save(self, order_return: OrderReturn) -> None:
        self._returns.append(order_return)

    async def get_recent(self, limit: int = 50, offset: int = 0) -> list[ReturnRecord]:
        ordered = sorted(self._returns, key=lambda r: r.created_at, reverse=True)
        page = ordered[offset : offset + limit]
        return [
            ReturnRecord(
                external_id=r.external_id,
                marketplace=r.marketplace,
                order_external_id=r.order_external_id,
                buyer_login=r.buyer_login,
                status=r.status,
                products_summary=r.products_summary,
                return_date=r.created_at,
            )
            for r in page
        ]
