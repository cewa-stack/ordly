"""Kontrakt dostępu do wykrytych maili marketplace, niezależny od bazy danych."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.entities.mail_message import MailMessage


class MailRepository(ABC):
    """Serwisy zależą wyłącznie od tego interfejsu - implementacja SQLite w repositories/."""

    @abstractmethod
    async def exists(self, message_id: str) -> bool:
        """Sprawdza, czy mail o danym Message-ID jest już zapisany."""
        raise NotImplementedError

    @abstractmethod
    async def save(self, message: MailMessage) -> None:
        """Zapisuje nowo wykryty mail."""
        raise NotImplementedError

    @abstractmethod
    async def get_recent(
        self,
        source: str | None = None,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MailMessage]:
        """Zwraca ostatnie maile (opcjonalnie filtrowane), najnowsze pierwsze."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, message_id: str) -> MailMessage | None:
        """Zwraca pojedynczy mail po Message-ID."""
        raise NotImplementedError

    @abstractmethod
    async def mark_read(self, message_id: str) -> None:
        """Oznacza mail jako przeczytany."""
        raise NotImplementedError

    @abstractmethod
    async def get_latest_received_at(self) -> datetime | None:
        """Zwraca datę najnowszego zapisanego maila - punkt startowy kolejnej synchronizacji."""
        raise NotImplementedError
