"""Abstrakcja dostępu do zapisanych tokenów OAuth2 dla dowolnego marketplace."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class StoredTokens:
    """Reprezentacja zaszyfrowanych tokenów odczytanych z bazy danych."""

    encrypted_access_token: str
    encrypted_refresh_token: str
    expires_at: datetime


class TokenStore(ABC):
    """
    Kontrakt dostępu do przechowywanych tokenów OAuth2.

    Pluginy (np. AllegroPlugin) zależą wyłącznie od tego interfejsu,
    nigdy od konkretnej implementacji SQLite.
    """

    @abstractmethod
    async def get_tokens(self, marketplace: str) -> StoredTokens | None:
        """Zwraca zapisane tokeny dla danego marketplace lub None, jeśli brak."""
        raise NotImplementedError

    @abstractmethod
    async def save_tokens(
        self,
        marketplace: str,
        encrypted_access_token: str,
        encrypted_refresh_token: str,
        expires_at: datetime,
    ) -> None:
        """Zapisuje (nadpisuje) tokeny dla danego marketplace."""
        raise NotImplementedError
