"""Model ORM tabeli produktów magazynowych (IMS)."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.database.models.inventory_movement_model import InventoryMovementModel


class InventoryItemModel(Base, TimestampMixin):
    """
    Tabela `inventory_items`.

    Centralny magazyn ORDLY - jeden wiersz to jeden fizyczny produkt
    (SKU), niezależny od ofert marketplace, na których jest sprzedawany.
    """

    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    ean: Mapped[str | None] = mapped_column(String(20), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stock: Mapped[int] = mapped_column(nullable=False, default=0)
    min_stock: Mapped[int] = mapped_column(nullable=False, default=0)
    max_stock: Mapped[int | None] = mapped_column(nullable=True)
    purchase_cost: Mapped[Decimal | None] = mapped_column(nullable=True)
    sale_price: Mapped[Decimal | None] = mapped_column(nullable=True)
    location: Mapped[str | None] = mapped_column(String(100), nullable=True)

    #: Produkt główny, z którym ten produkt porusza się w parze przy
    #: sprzedaży (butelka -> nakrętka, kroplomierz). NULL oznacza produkt
    #: samodzielny albo sam będący produktem głównym.
    #:
    #: Celowo BEZ `relationship()` w obie strony: repozytorium czyta
    #: podprodukty jawnym zapytaniem, a nieużywana relacja w aplikacji
    #: asynchronicznej to tylko ryzyko przypadkowego leniwego ładowania
    #: poza greenletem (MissingGreenlet). Encja domenowa i tak operuje
    #: na SKU, nie na identyfikatorach bazodanowych.
    parent_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True, index=True
    )

    movements: Mapped[list[InventoryMovementModel]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )
