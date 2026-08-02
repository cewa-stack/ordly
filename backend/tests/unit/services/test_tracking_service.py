"""Testy jednostkowe TrackingService."""

from __future__ import annotations

import pytest

from app.domain.exceptions.domain_exceptions import OrderNotFoundError
from app.services.tracking_service import TrackingService


class FakeShipmentRepository:
    """Minimalny fake ShipmentRepository na potrzeby tego testu."""

    def __init__(self) -> None:
        self.saved_results: list[tuple[str, object]] = []

    async def save_check_result(self, order_external_id, shipment) -> None:
        self.saved_results.append((order_external_id, shipment))

    async def get_last_known(self, order_external_id):
        return None


class TestTrackingService:
    """Testy pobierania statusu przesyłki na żądanie."""

    @pytest.mark.asyncio
    async def test_rzuca_order_not_found_gdy_zamowienie_nie_istnieje(
        self, fake_marketplace_plugin, fake_order_repository
    ):
        """Sprawdzenie przesyłki dla nieznanego zamówienia powinno zawieść jasno."""
        shipment_repository = FakeShipmentRepository()
        service = TrackingService(
            fake_marketplace_plugin, fake_order_repository, shipment_repository
        )

        with pytest.raises(OrderNotFoundError):
            await service.get_current_tracking("NIEISTNIEJACE-999")

    @pytest.mark.asyncio
    async def test_zapisuje_wynik_sprawdzenia_do_repozytorium(
        self, fake_marketplace_plugin, fake_order_repository, sample_order
    ):
        """Udane sprawdzenie statusu powinno zostać zapisane jako historia."""
        await fake_order_repository.save(sample_order)
        shipment_repository = FakeShipmentRepository()
        service = TrackingService(
            fake_marketplace_plugin, fake_order_repository, shipment_repository
        )

        shipment = await service.get_current_tracking(sample_order.external_id)

        assert shipment.tracking_number == "TEST123456"
        assert len(shipment_repository.saved_results) == 1
