"""
Serwis automatycznego wykrywania numeru przesyłki - odpowiednik komendy
/tracking, ale wywoływany cyklicznie zamiast na żądanie użytkownika.

Celowo NIE dotyka `fulfillment_status` - ten pozostaje sterowany
wyłącznie przez SyncOrdersService na podstawie realnego stanu z Allegro
(patrz app/domain/entities/order.py). Ten serwis tylko dogrywa
`shipments.tracking_number`, gdy Allegro już go przydzieliło (np. po
wygenerowaniu etykiety InPost), żeby interfejs mógł pokazać zamówienie
jako wysłane bez czekania na ręczną zmianę statusu na Allegro.
"""

from __future__ import annotations

from datetime import timedelta

from loguru import logger

from app.domain.exceptions.domain_exceptions import (
    MarketplaceUnavailableError,
    ShipmentNotAvailableError,
)
from app.domain.interfaces.marketplace_plugin import MarketplacePlugin
from app.domain.interfaces.order_repository import OrderRepository
from app.domain.interfaces.shipment_repository import ShipmentRepository
from app.services.tracking_service import TrackingService
from app.utils.time import utc_now

_CANDIDATE_WINDOW_DAYS = 30


class WaybillCheckService:
    """Dogrywa numery przesyłek dla zamówień, które jeszcze ich nie mają."""

    def __init__(
        self,
        plugin: MarketplacePlugin,
        order_repository: OrderRepository,
        shipment_repository: ShipmentRepository,
    ) -> None:
        self._order_repository = order_repository
        self._tracking_service = TrackingService(plugin, order_repository, shipment_repository)

    async def check_new_waybills(self) -> int:
        """
        Sprawdza otwarte zamówienia i zapisuje nowo pojawione numery przesyłek.

        Kandydaci to zamówienia bez numeru przesyłki i bez statusu
        realizacji oznaczającego wysyłkę, z ostatnich 30 dni -
        `get_unshipped_since` już wyklucza anulowane i te z zapisanym
        `tracking_number` (patrz OrderRepository.get_unshipped_since).

        Returns:
            Liczbę zamówień, dla których właśnie wykryto numer przesyłki.
        """
        since = utc_now() - timedelta(days=_CANDIDATE_WINDOW_DAYS)
        candidates = await self._order_repository.get_unshipped_since(since)

        detected = 0
        for order in candidates:
            try:
                shipment = await self._tracking_service.get_current_tracking(order.external_id)
            except ShipmentNotAvailableError:
                continue
            except MarketplaceUnavailableError:
                logger.warning(
                    "Allegro API niedostępne przy sprawdzaniu numerów przesyłek - "
                    "przerywam cykl, spróbuję przy następnym uruchomieniu"
                )
                break

            if shipment.tracking_number:
                detected += 1
                logger.info(
                    "Wykryto numer przesyłki dla zamówienia {}: {}",
                    order.external_id,
                    shipment.tracking_number,
                )

        return detected
