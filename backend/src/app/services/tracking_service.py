"""Serwis obsługi statusu przesyłek - wyłącznie na żądanie użytkownika."""

from __future__ import annotations

from loguru import logger

from app.domain.entities.shipment import Shipment
from app.domain.exceptions.domain_exceptions import (
    MarketplaceUnavailableError,
    OrderNotFoundError,
    ShipmentNotAvailableError,
)
from app.domain.interfaces.marketplace_plugin import MarketplacePlugin
from app.domain.interfaces.order_repository import OrderRepository
from app.domain.interfaces.shipment_repository import ShipmentRepository
from app.infrastructure.plugins.allegro.exceptions import AllegroApiError

_NOT_YET_SHIPPED_STATUS = "PRZYGOTOWYWANA"


class TrackingService:
    """
    Pobiera aktualny status przesyłki bezpośrednio z marketplace.

    Status NIE jest cache'owany do celów wyświetlania - każde wywołanie
    get_current_tracking() wykonuje realne zapytanie do API marketplace.
    """

    def __init__(
        self,
        plugin: MarketplacePlugin,
        order_repository: OrderRepository,
        shipment_repository: ShipmentRepository,
    ) -> None:
        self._plugin = plugin
        self._order_repository = order_repository
        self._shipment_repository = shipment_repository

    async def get_current_tracking(self, order_external_id: str) -> Shipment:
        """
        Pobiera aktualny status przesyłki dla zamówienia.

        Args:
            order_external_id: Numer zamówienia podany przez użytkownika.

        Returns:
            Aktualny stan przesyłki pobrany "na żywo" z marketplace.

        Raises:
            OrderNotFoundError: Gdy zamówienie nie istnieje w naszej bazie.
            ShipmentNotAvailableError: Gdy sprzedawca jeszcze nie nadał paczki.
            MarketplaceUnavailableError: Gdy marketplace API nie odpowiada.
        """
        order = await self._order_repository.get_by_external_id(order_external_id)
        if order is None:
            raise OrderNotFoundError(order_external_id)

        try:
            shipment = await self._plugin.get_tracking(order_external_id)
        except AllegroApiError as exc:
            logger.warning(
                "Allegro API niedostępne przy sprawdzaniu przesyłki {} - "
                "próba użycia ostatniego znanego statusu z bazy",
                order_external_id,
            )
            fallback = await self._shipment_repository.get_last_known(order_external_id)
            if fallback is not None:
                return fallback
            raise MarketplaceUnavailableError(str(exc)) from exc

        await self._shipment_repository.save_check_result(order_external_id, shipment)

        if shipment.status == _NOT_YET_SHIPPED_STATUS:
            raise ShipmentNotAvailableError(order_external_id)

        return shipment
