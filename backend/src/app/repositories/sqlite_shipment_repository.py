"""Implementacja ShipmentRepository oparta o SQLite (tabela shipments)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.order_model import OrderModel
from app.database.models.shipment_model import ShipmentModel
from app.domain.entities.shipment import Shipment
from app.domain.interfaces.shipment_repository import ShipmentRepository
from app.utils.time import utc_now


class SqliteShipmentRepository(ShipmentRepository):
    """Zapisuje i odczytuje historię ręcznych sprawdzeń statusu przesyłek."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_check_result(self, order_external_id: str, shipment: Shipment) -> None:
        """
        Zapisuje wynik sprawdzenia statusu, tworząc lub aktualizując wiersz.
        """
        order_stmt = select(OrderModel.id).where(OrderModel.external_id == order_external_id)
        order_result = await self._session.execute(order_stmt)
        order_id = order_result.scalar_one_or_none()
        if order_id is None:
            return

        checked_at = utc_now()
        stmt = sqlite_insert(ShipmentModel).values(
            order_id=order_id,
            carrier=shipment.carrier,
            tracking_number=shipment.tracking_number,
            status=shipment.status,
            last_checked_at=checked_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["order_id"],
            set_={
                "carrier": shipment.carrier,
                "tracking_number": shipment.tracking_number,
                "status": shipment.status,
                "last_checked_at": checked_at,
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_last_known(self, order_external_id: str) -> Shipment | None:
        """Zwraca ostatni zapisany wynik sprawdzenia statusu przesyłki."""
        stmt = (
            select(ShipmentModel)
            .join(OrderModel, ShipmentModel.order_id == OrderModel.id)
            .where(OrderModel.external_id == order_external_id)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None

        return Shipment(
            order_external_id=order_external_id,
            carrier=model.carrier,
            tracking_number=model.tracking_number,
            status=model.status,
            updated_at=model.last_checked_at,
        )
