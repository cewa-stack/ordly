"""Model ORM tabeli mapowań ofert marketplace na produkty magazynowe."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.database.models.inventory_item_model import InventoryItemModel


class OfferLinkModel(Base, TimestampMixin):
    """
    Tabela `offer_links`.

    Wiąże produkt z oferty marketplace (external_product_id) ze
    składnikami magazynowymi. Zwykła oferta ma jeden wiersz (quantity=1),
    zestaw (np. Starter Kit) ma wiele wierszy - po jednym na składnik.
    """

    __tablename__ = "offer_links"
    __table_args__ = (
        UniqueConstraint(
            "marketplace", "external_product_id", "item_id", name="uq_offer_link"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    marketplace: Mapped[str] = mapped_column(String(50), nullable=False)
    external_product_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(nullable=False, default=1)

    item: Mapped[InventoryItemModel] = relationship()
