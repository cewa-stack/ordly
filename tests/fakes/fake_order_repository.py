"""Fake implementacja OrderRepository - działa w pamięci, bez bazy danych."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.domain.entities.order import Order
from app.domain.fulfillment import (
    ACTIVE_FULFILLMENT_STATUSES,
    SHIPPED_FULFILLMENT_STATUSES,
)
from app.domain.interfaces.order_repository import OrderRepository


class FakeOrderRepository(OrderRepository):
    """
    Implementacja OrderRepository trzymająca dane w zwykłej liście Pythona.

    Używana w testach jednostkowych serwisów, żeby nie zależeć od
    prawdziwej bazy danych.
    """

    def __init__(self) -> None:
        self._orders: list[Order] = []
        self._notified: set[tuple[str, str]] = set()

    async def exists(self, marketplace: str, external_id: str) -> bool:
        return any(
            o.marketplace == marketplace and o.external_id == external_id
            for o in self._orders
        )

    async def save(self, order: Order) -> None:
        self._orders.append(order)

    async def get_by_external_id(self, external_id: str) -> Order | None:
        return next((o for o in self._orders if o.external_id == external_id), None)

    async def get_recent(self, limit: int, offset: int = 0) -> list[Order]:
        ordered = sorted(self._orders, key=lambda o: o.order_date, reverse=True)
        return ordered[offset : offset + limit]

    async def get_unshipped_since(self, since: datetime) -> list[Order]:
        unshipped = [
            o
            for o in self._orders
            if o.order_date >= since
            and o.status.upper() != "CANCELLED"
            and (
                o.fulfillment_status is None
                or o.fulfillment_status.upper() not in SHIPPED_FULFILLMENT_STATUSES
            )
        ]
        return sorted(unshipped, key=lambda o: o.order_date, reverse=True)

    async def get_active(self, limit: int) -> list[Order]:
        active = [
            o
            for o in self._orders
            if o.status.upper() != "CANCELLED"
            and o.fulfillment_status is not None
            and o.fulfillment_status.upper() in ACTIVE_FULFILLMENT_STATUSES
        ]
        return sorted(active, key=lambda o: o.order_date, reverse=True)[:limit]

    async def search(self, query: str) -> list[Order]:
        query_lower = query.lower()
        return [
            o
            for o in self._orders
            if query_lower in o.external_id.lower()
            or query_lower in o.buyer.login.lower()
            or any(query_lower in p.name.lower() for p in o.products)
        ]

    async def count_since(self, since: datetime) -> int:
        return sum(1 for o in self._orders if o.order_date >= since)

    async def sum_amount_since(self, since: datetime) -> float:
        return float(sum(o.total_amount for o in self._orders if o.order_date >= since))

    async def count_all(self) -> int:
        return len(self._orders)

    async def sum_amount_by_day(self, since: datetime) -> dict[str, float]:
        totals: dict[str, float] = {}
        for order in self._orders:
            if order.order_date < since:
                continue
            key = order.order_date.strftime("%Y-%m-%d")
            totals[key] = totals.get(key, 0.0) + float(order.total_amount)
        return totals

    async def update_status(
        self, marketplace: str, external_id: str, status: str
    ) -> None:
        self._orders = [
            replace(o, status=status)
            if o.marketplace == marketplace and o.external_id == external_id
            else o
            for o in self._orders
        ]

    async def update_fulfillment_status(
        self, marketplace: str, external_id: str, fulfillment_status: str | None
    ) -> None:
        self._orders = [
            replace(o, fulfillment_status=fulfillment_status)
            if o.marketplace == marketplace and o.external_id == external_id
            else o
            for o in self._orders
        ]

    async def mark_as_notified(self, marketplace: str, external_id: str) -> None:
        self._notified.add((marketplace, external_id))

    def is_notified(self, marketplace: str, external_id: str) -> bool:
        """Metoda pomocnicza tylko dla testów - sprawdza znacznik powiadomienia."""
        return (marketplace, external_id) in self._notified
