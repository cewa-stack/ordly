"""Model ORM tabeli znaczników synchronizacji magazynu."""

from __future__ import annotations

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class StockSyncModel(Base, TimestampMixin):
    """
    Tabela `stock_syncs`.

    Rejestr przetworzonych operacji magazynowych - unique constraint
    (marketplace, reference, operation) to identyfikator synchronizacji,
    który chroni przed podwójnym odjęciem/przywróceniem stanów dla tego
    samego zamówienia lub zwrotu.
    """

    __tablename__ = "stock_syncs"
    __table_args__ = (
        UniqueConstraint(
            "marketplace", "reference", "operation", name="uq_stock_sync_operation"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    marketplace: Mapped[str] = mapped_column(String(50), nullable=False)
    reference: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(30), nullable=False)
