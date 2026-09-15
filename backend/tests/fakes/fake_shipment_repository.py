"""Fake implementacja ShipmentRepository - działa w pamięci, bez bazy danych."""

from __future__ import annotations

from app.domain.entities.shipment import Shipment
from app.domain.interfaces.shipment_repository import ShipmentRepository


class FakeShipmentRepository(ShipmentRepository):
    """Trzyma ostatni zapisany wynik sprawdzenia przesyłki per zamówienie."""

    def __init__(self) -> None:
        self.saved_results: list[tuple[str, Shipment]] = []
        self._by_order: dict[str, Shipment] = {}

    async def save_check_result(self, order_external_id: str, shipment: Shipment) -> None:
        self.saved_results.append((order_external_id, shipment))
        self._by_order[order_external_id] = shipment

    async def get_last_known(self, order_external_id: str) -> Shipment | None:
        return self._by_order.get(order_external_id)
