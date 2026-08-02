"""Abstrakcja historii wysłanych wiadomości SMS (ochrona przed dublowaniem)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.sms_message import SmsRecord


class SmsHistoryRepository(ABC):
    """
    Kontrakt zapisu i odczytu historii wiadomości SMS.

    Historia pełni dwie role: audyt (co i kiedy wysłano) oraz gwarancję,
    że dany typ wiadomości (np. PACKING_STARTED) wychodzi do klienta
    dokładnie raz na zamówienie.
    """

    @abstractmethod
    async def was_sent_successfully(self, order_external_id: str, message_type: str) -> bool:
        """Czy dla zamówienia zapisano już pomyślnie wysłany SMS danego typu."""
        raise NotImplementedError

    @abstractmethod
    async def record(self, record: SmsRecord) -> None:
        """Zapisuje wynik próby wysyłki (wysłany, nieudany lub pominięty)."""
        raise NotImplementedError
