"""Abstrakcja rejestru wiadomości wysłanych przez bota (nocne czyszczenie)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrackedMessage:
    """Identyfikator pojedynczej wiadomości wysłanej przez bota na czat."""

    chat_id: int
    message_id: int


class TelegramMessageRepository(ABC):
    """
    Kontrakt zapisu i odczytu identyfikatorów wiadomości bota.

    Telegram pozwala botowi usuwać wyłącznie wiadomości, które sam wysłał
    i których identyfikatory zna - dlatego każda wysłana wiadomość jest tu
    rejestrowana, a nocne czyszczenie odczytuje i usuwa je hurtowo.
    """

    @abstractmethod
    async def record(self, chat_id: int, message_id: int) -> None:
        """Zapisuje identyfikator wiadomości wysłanej na czat."""
        raise NotImplementedError

    @abstractmethod
    async def get_all(self) -> list[TrackedMessage]:
        """Zwraca wszystkie zarejestrowane wiadomości (od najstarszej)."""
        raise NotImplementedError

    @abstractmethod
    async def delete_all(self) -> int:
        """Usuwa cały rejestr wiadomości. Zwraca liczbę usuniętych wpisów."""
        raise NotImplementedError
