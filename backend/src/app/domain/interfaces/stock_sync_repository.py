"""Abstrakcja znaczników synchronizacji magazynu (ochrona przed podwójnym odjęciem)."""

from __future__ import annotations

from abc import ABC, abstractmethod


class StockSyncRepository(ABC):
    """
    Kontrakt rejestru przetworzonych operacji magazynowych.

    Para (marketplace, reference, operation) jest identyfikatorem
    synchronizacji - zapisana raz, blokuje ponowne wykonanie tej samej
    operacji (np. podwójne odjęcie stanu dla jednego zamówienia).
    """

    @abstractmethod
    async def was_processed(self, marketplace: str, reference: str, operation: str) -> bool:
        """Sprawdza, czy operacja dla danego dokumentu została już wykonana."""
        raise NotImplementedError

    @abstractmethod
    async def mark_processed(self, marketplace: str, reference: str, operation: str) -> bool:
        """
        Rejestruje wykonanie operacji.

        Returns:
            True, gdy znacznik został właśnie zapisany; False, gdy operacja
            była już wcześniej zarejestrowana (nie wolno jej powtarzać).
        """
        raise NotImplementedError
