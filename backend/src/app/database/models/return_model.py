"""Model ORM tabeli zwrotów klientów."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class ReturnModel(Base, TimestampMixin):
    """
    Tabela `customer_returns`.

    Unikalność (marketplace, external_id) gwarantuje, że ten sam
    zwrot z tego samego marketplace nigdy nie zostanie zapisany
    dwa razy - a więc powiadomienie o nim wyjdzie tylko raz.

    Produkty zwrotu przechowywane są jako gotowe podsumowanie
    tekstowe (products_summary) - system nie potrzebuje ich w formie
    relacyjnej, służą wyłącznie do treści powiadomienia.
    """

    __tablename__ = "customer_returns"
    __table_args__ = (
        UniqueConstraint(
            "marketplace", "external_id", name="uq_return_marketplace_external_id"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    marketplace: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    order_external_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    buyer_login: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    products_summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    return_date: Mapped[datetime] = mapped_column(nullable=False)
