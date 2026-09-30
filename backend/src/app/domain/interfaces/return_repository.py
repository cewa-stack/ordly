"""Abstrakcyjny kontrakt dostępu do danych zwrotów klientów."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.order_return import OrderReturn, ReturnRecord


class ReturnRepository(ABC):
    """
    Kontrakt dostępu do zwrotów, niezależny od technologii bazy danych.

    Serwisy zależą wyłącznie od tego interfejsu - implementacja
    SQLite żyje w repositories/sqlite_return_repository.py.
    """

    @abstractmethod
    async def exists(self, marketplace: str, external_id: str) -> bool:
        """Sprawdza, czy zwrot o danym numerze jest już zapisany."""
        raise NotImplementedError

    @abstractmethod
    async def save(self, order_return: OrderReturn) -> None:
        """
        Zapisuje nowy zwrot.

        Raises:
            DuplicateReturnError: Gdy zwrot o tym samym
                (marketplace, external_id) już istnieje.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_recent(self, limit: int = 50, offset: int = 0) -> list[ReturnRecord]:
        """Zwraca ostatnie zwroty do wyświetlenia, najnowsze pierwsze."""
        raise NotImplementedError

    @abstractmethod
    async def get_status(self, marketplace: str, external_id: str) -> str | None:
        """Zwraca zapisany status zwrotu albo None, gdy zwrotu nie ma."""
        raise NotImplementedError

    @abstractmethod
    async def update_status(self, marketplace: str, external_id: str, status: str) -> None:
        """Utrwala nowy status zwrotu wykryty podczas synchronizacji."""
        raise NotImplementedError

    @abstractmethod
    async def get_open(self, marketplace: str, limit: int) -> list[ReturnRecord]:
        """
        Zwraca zwroty danego marketplace z niezamkniętym statusem
        (poza CLOSED_RETURN_STATUSES), najnowsze pierwsze.

        Służy synchronizacji do dopytania o zwroty, których nie było
        w pobranej liście - inaczej ich status zamarzałby w bazie.
        """
        raise NotImplementedError
