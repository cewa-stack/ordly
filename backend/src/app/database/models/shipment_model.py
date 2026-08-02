"""Model ORM tabeli przesyłek."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.database.models.order_model import OrderModel


class ShipmentModel(Base, TimestampMixin):
    """
    Tabela `shipments`.

    Status przesyłki NIE jest synchronizowany automatycznie - ten
    wiersz jest tworzony/aktualizowany wyłącznie na żądanie
    użytkownika przez komendę /tracking.
    """

    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    carrier: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tracking_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(nullable=True)

    order: Mapped[OrderModel] = relationship(back_populates="shipment")
