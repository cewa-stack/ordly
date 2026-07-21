"""Abstrakcyjny kontrakt dostępu do danych zamówień."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.entities.order import Order


class OrderRepository(ABC):
    """
    Kontrakt dostępu do zamówień, niezależny od technologii bazy danych.

    Serwisy zależą wyłącznie od tego interfejsu - implementacja
    SQLite żyje w repositories/sqlite_order_repository.py.
    """

    @abstractmethod
    async def exists(self, marketplace: str, external_id: str) -> bool:
        """Sprawdza, czy zamówienie o danym numerze jest już zapisane."""
        raise NotImplementedError

    @abstractmethod
    async def save(self, order: Order) -> None:
        """
        Zapisuje nowe zamówienie wraz z produktami.

        Raises:
            DuplicateOrderError: Gdy zamówienie o tym samym
                (marketplace, external_id) już istnieje.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_by_external_id(self, external_id: str) -> Order | None:
        """Zwraca zamówienie po jego numerze zewnętrznym lub None, jeśli brak."""
        raise NotImplementedError

    @abstractmethod
    async def get_recent(self, limit: int) -> list[Order]:
        """Zwraca ostatnie zamówienia posortowane od najnowszego."""
        raise NotImplementedError

    @abstractmethod
    async def get_unshipped_since(self, since: datetime) -> list[Order]:
        """
        Zwraca zamówienia utworzone od podanej daty, które nie zostały
        jeszcze wysłane.

        Zamówienie uznaje się za wysłane, gdy jego status realizacji to
        SENT/PICKED_UP lub gdy ma zapisany numer przewozowy. Zamówienia
        anulowane są pomijane - nie wymagają wysyłki. Używane przez
        przypomnienie o niewysłanych zamówieniach (20:00).
        """
        raise NotImplementedError

    @abstractmethod
    async def get_active(self, limit: int) -> list[Order]:
        """
        Zwraca aktywne zamówienia (nowe lub w trakcie pakowania),
        posortowane od najnowszego.

        Pomija zamówienia wysłane, anulowane i zwrócone. Używane przez
        nocne czyszczenie czatu (02:00) do ponownej publikacji wyłącznie
        aktualnych zamówień.
        """
        raise NotImplementedError

    @abstractmethod
    async def search(self, query: str) -> list[Order]:
        """Wyszukuje zamówienia po numerze, kupującym lub nazwie produktu."""
        raise NotImplementedError

    @abstractmethod
    async def count_since(self, since: datetime) -> int:
        """Zwraca liczbę zamówień utworzonych od podanej daty."""
        raise NotImplementedError

    @abstractmethod
    async def sum_amount_since(self, since: datetime) -> float:
        """Zwraca sumę kwot zamówień od podanej daty."""
        raise NotImplementedError

    @abstractmethod
    async def count_all(self) -> int:
        """Zwraca łączną liczbę zamówień w bazie."""
        raise NotImplementedError

    @abstractmethod
    async def update_status(
        self, marketplace: str, external_id: str, status: str
    ) -> None:
        """
        Aktualizuje status istniejącego zamówienia.

        Wywoływane przez synchronizację, gdy marketplace zwróci inny
        status niż zapisany w bazie (np. anulowanie zamówienia).
        """
        raise NotImplementedError

    @abstractmethod
    async def update_fulfillment_status(
        self, marketplace: str, external_id: str, fulfillment_status: str | None
    ) -> None:
        """
        Aktualizuje status realizacji (fulfillment) istniejącego zamówienia.

        Wywoływane przez synchronizację, gdy Allegro zwróci inny etap
        realizacji niż zapisany w bazie (np. NEW -> PROCESSING -> SENT).
        """
        raise NotImplementedError

    @abstractmethod
    async def mark_as_notified(self, marketplace: str, external_id: str) -> None:
        """
        Oznacza zamówienie jako powiadomione (ustawia notified_at = teraz).

        Wywoływane po pomyślnej wysyłce powiadomienia Telegram.
        """
        raise NotImplementedError
