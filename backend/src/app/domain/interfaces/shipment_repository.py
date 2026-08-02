"""Abstrakcyjny kontrakt zapisu historii sprawdzeń statusu przesyłek."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.shipment import Shipment


class ShipmentRepository(ABC):
    """
    Kontrakt zapisu wyników ręcznego sprawdzenia statusu przesyłki.

    Nie służy do automatycznej synchronizacji (projekt tego nie robi) -
    wyłącznie do zachowania historii tego, co użytkownik sprawdził
    komendą /tracking, oraz jako fallback, gdy Allegro API jest
    chwilowo niedostępne.
    """

    @abstractmethod
    async def save_check_result(self, order_external_id: str, shipment: Shipment) -> None:
        """Zapisuje (nadpisuje) wynik ostatniego sprawdzenia statusu przesyłki."""
        raise NotImplementedError

    @abstractmethod
    async def get_last_known(self, order_external_id: str) -> Shipment | None:
        """Zwraca ostatnio zapisany wynik sprawdzenia lub None, jeśli brak historii."""
        raise NotImplementedError
