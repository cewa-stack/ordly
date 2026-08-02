"""Model ORM tabeli produktów przypisanych do zamówienia."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.database.models.order_model import OrderModel


class ProductModel(Base, TimestampMixin):
    """
    Tabela `products`.

    Każdy wiersz reprezentuje jedną pozycję (produkt) w konkretnym
    zamówieniu - relacja wiele-do-jednego z OrderModel.
    """

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_product_id: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(nullable=False)

    order: Mapped[OrderModel] = relationship(back_populates="products")
