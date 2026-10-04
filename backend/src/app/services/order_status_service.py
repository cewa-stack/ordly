"""
Ręczna zmiana statusu aplikacyjnego zamówienia.

Status aplikacyjny (Nowe / W realizacji / Zrealizowane / Anulowane) żyje
wyłącznie w ORDLY - ta usługa NIE wywołuje Allegro. Regułę priorytetu
wobec statusu Allegro opisuje app/domain/order_status.py.
"""

from __future__ import annotations

from loguru import logger

from app.domain.entities.order import Order
from app.domain.exceptions.domain_exceptions import OrderNotFoundError
from app.domain.interfaces.order_repository import OrderRepository
from app.domain.order_status import (
    APP_STATUS_SOURCE_MANUAL,
    APP_STATUS_SOURCE_RESTORE,
    OrderStatusChange,
    allegro_app_status,
    effective_app_status,
    is_valid_app_status,
)
from app.utils.time import utc_now


class InvalidAppStatusError(ValueError):
    """Wartość spoza czterech statusów aplikacyjnych."""


class OrderStatusService:
    """Ustawia i przywraca status aplikacyjny, zapisując historię zmian."""

    def __init__(self, order_repository: OrderRepository) -> None:
        self._orders = order_repository

    async def set_app_status(self, external_id: str, status: str | None) -> Order:
        """
        Ustawia ręczny status aplikacyjny albo (`status=None`) przywraca
        status wynikający z Allegro.

        Zapisuje razem z nim `basis` - status z Allegro w tej chwili - żeby
        reguła priorytetu wiedziała, czy Allegro później coś zmieniło.
        Każda zmiana trafia do historii (`order_status_changes`).

        Raises:
            OrderNotFoundError: Gdy zamówienia nie ma w bazie.
            InvalidAppStatusError: Gdy status nie jest jednym z czterech.
        """
        if status is not None and not is_valid_app_status(status):
            raise InvalidAppStatusError(status)

        order = await self._orders.get_by_external_id(external_id)
        if order is None:
            raise OrderNotFoundError(external_id)

        previous = effective_app_status(order)
        now = utc_now()
        if status is None:
            await self._orders.set_app_status(order.marketplace, external_id, None, None, None)
            source = APP_STATUS_SOURCE_RESTORE
        else:
            basis = allegro_app_status(
                order.status, order.fulfillment_status, order.tracking_number
            )
            await self._orders.set_app_status(order.marketplace, external_id, status, basis, now)
            source = APP_STATUS_SOURCE_MANUAL

        updated = await self._orders.get_by_external_id(external_id)
        assert updated is not None
        await self._orders.record_app_status_change(
            OrderStatusChange(
                marketplace=order.marketplace,
                order_external_id=external_id,
                previous_status=previous,
                new_status=effective_app_status(updated),
                source=source,
                changed_at=now,
            )
        )
        logger.info(
            "Zamówienie {}: status aplikacyjny {} -> {} ({})",
            external_id,
            previous,
            effective_app_status(updated),
            source,
        )
        return updated

    async def history(self, external_id: str) -> list[OrderStatusChange]:
        """Historia zmian statusu aplikacyjnego zamówienia, od najnowszej."""
        if await self._orders.get_by_external_id(external_id) is None:
            raise OrderNotFoundError(external_id)
        return await self._orders.get_app_status_history(external_id)
