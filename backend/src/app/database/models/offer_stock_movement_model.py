"""Model ORM historii ręcznych zmian ilości przy ofercie."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class OfferStockMovementModel(Base, TimestampMixin):
    """
    Tabela `offer_stock_movements`.

    Zapis każdego ręcznego wpisania ilości przy ofercie. Tylko ręcznego -
    ORDLY nie odejmuje już stanów przy sprzedaży, więc nie ma tu kolumn
    `source` ani `reference`: każdy wiersz pochodzi od użytkownika.
    """

    __tablename__ = "offer_stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    offer_id: Mapped[int] = mapped_column(
        ForeignKey("marketplace_offers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    #: Różnica względem poprzedniej ilości. NULL przy pierwszym wpisie,
    #: bo "z niczego na 120 szt." nie jest zmianą o 120 - poprzedni stan
    #: nie był znany i pokazanie "+120" sugerowałoby dostawę.
    change: Mapped[int | None] = mapped_column(nullable=True)

    quantity_after: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
