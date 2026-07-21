"""Model ORM tabeli zamówień."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.database.models.product_model import ProductModel
    from app.database.models.shipment_model import ShipmentModel


class OrderModel(Base, TimestampMixin):
    """
    Tabela `orders`.

    Unikalność (marketplace, external_id) gwarantuje, że to samo
    zamówienie z tego samego marketplace nigdy nie zostanie zapisane
    dwa razy.
    """

    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("marketplace", "external_id", name="uq_order_marketplace_external_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    marketplace: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    buyer_login: Mapped[str] = mapped_column(String(255), nullable=False)
    buyer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    buyer_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="PLN", nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    fulfillment_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )
    order_date: Mapped[datetime] = mapped_column(nullable=False)
    notified_at: Mapped[datetime | None] = mapped_column(nullable=True, index=True)
    raw_payload_json: Mapped[str | None] = mapped_column(nullable=True)

    products: Mapped[list[ProductModel]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    shipment: Mapped[ShipmentModel | None] = relationship(
        back_populates="order", cascade="all, delete-orphan", uselist=False
    )
