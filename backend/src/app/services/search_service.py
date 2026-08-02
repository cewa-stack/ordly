"""Serwis wyszukiwania zamówień dla komendy /search."""

from __future__ import annotations

from app.domain.entities.order import Order
from app.domain.interfaces.order_repository import OrderRepository


class SearchService:
    """Wyszukuje zamówienia po dowolnym fragmencie tekstu."""

    def __init__(self, order_repository: OrderRepository) -> None:
        self._order_repository = order_repository

    async def search_orders(self, query: str) -> list[Order]:
        """Deleguje wyszukiwanie do repozytorium (numer, kupujący, produkt)."""
        return await self._order_repository.search(query)
