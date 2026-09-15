"""Abstrakcyjny kontrakt zapisu historii sprawdzeń statusu przesyłek."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.shipment import Shipment


class ShipmentRepository(ABC):
    """
    Kontrakt zapisu wyników sprawdzenia statusu przesyłki.

    Zasila historię tego, co użytkownik sprawdził komendą /tracking,
    oraz to, co automatycznie wykrył `check_waybills_job` - a także
    działa jako fallback, gdy Allegro API jest chwilowo niedostępne.
    """

    @abstractmethod
    async def save_check_result(self, order_external_id: str, shipment: Shipment) -> None:
        """Zapisuje (nadpisuje) wynik ostatniego sprawdzenia statusu przesyłki."""
        raise NotImplementedError

    @abstractmethod
    async def get_last_known(self, order_external_id: str) -> Shipment | None:
        """Zwraca ostatnio zapisany wynik sprawdzenia lub None, jeśli brak historii."""
        raise NotImplementedError
