"""Fake implementacja ReturnRepository - działa w pamięci, bez bazy danych."""

from __future__ import annotations

from dataclasses import replace

from app.domain.entities.order_return import OrderReturn, ReturnRecord
from app.domain.interfaces.return_repository import ReturnRepository
from app.domain.returns import is_closed_return_status


class FakeReturnRepository(ReturnRepository):
    """
    Implementacja ReturnRepository trzymająca dane w zwykłej liście Pythona.

    Używana w testach jednostkowych serwisów, żeby nie zależeć od
    prawdziwej bazy danych.
    """

    def __init__(self) -> None:
        self._returns: list[OrderReturn] = []
        #: Status zamówienia po jego numerze - odpowiednik złączenia
        #: z tabelą orders w SqliteReturnRepository.
        self.order_statuses: dict[str, str] = {}

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
        return [self._record(r) for r in page]

    async def get_status(self, marketplace: str, external_id: str) -> str | None:
        return next(
            (
                r.status
                for r in self._returns
                if r.marketplace == marketplace and r.external_id == external_id
            ),
            None,
        )

    async def update_status(self, marketplace: str, external_id: str, status: str) -> None:
        self._returns = [
            (
                replace(r, status=status)
                if r.marketplace == marketplace and r.external_id == external_id
                else r
            )
            for r in self._returns
        ]

    async def get_open(self, marketplace: str, limit: int) -> list[ReturnRecord]:
        ordered = sorted(self._returns, key=lambda r: r.created_at, reverse=True)
        return [
            self._record(r)
            for r in ordered
            if r.marketplace == marketplace and not is_closed_return_status(r.status)
        ][:limit]

    def _record(self, r: OrderReturn) -> ReturnRecord:
        return ReturnRecord(
            external_id=r.external_id,
            marketplace=r.marketplace,
            order_external_id=r.order_external_id,
            buyer_login=r.buyer_login,
            status=r.status,
            products_summary=r.products_summary,
            return_date=r.created_at,
            order_status=self.order_statuses.get(r.order_external_id),
        )
