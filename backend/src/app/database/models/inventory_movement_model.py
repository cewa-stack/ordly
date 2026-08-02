"""Model ORM tabeli historii ruchów magazynowych."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.database.models.inventory_item_model import InventoryItemModel


class InventoryMovementModel(Base, TimestampMixin):
    """
    Tabela `inventory_movements`.

    Każda zmiana stanu magazynowego (ręczna korekta, sprzedaż, zwrot,
    anulowanie) jest osobnym wierszem - pełna, niemodyfikowalna historia.
    """

    __tablename__ = "inventory_movements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    change: Mapped[int] = mapped_column(nullable=False)
    stock_after: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)

    item: Mapped[InventoryItemModel] = relationship(back_populates="movements")
