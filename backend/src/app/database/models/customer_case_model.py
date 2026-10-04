"""Modele ORM rejestru anulowań i zwrotów pieniędzy."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class CustomerCaseModel(Base, TimestampMixin):
    """
    Tabela `customer_cases` - jeden rekord na zamówienie (patrz
    app/domain/customer_cases.py).

    Celowo BEZ telefonu, e-maila i imienia i nazwiska kupującego (decyzja
    użytkownika D7) - klienta identyfikuje login Allegro.
    """

    __tablename__ = "customer_cases"
    __table_args__ = (
        UniqueConstraint(
            "marketplace", "order_external_id", name="uq_customer_case_marketplace_order"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    marketplace: Mapped[str] = mapped_column(String(50), nullable=False)
    order_external_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    allegro_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    handling_status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    buyer_login: Mapped[str | None] = mapped_column(String(255), nullable=True)
    order_date: Mapped[datetime | None] = mapped_column(nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(nullable=True)
    reason: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    reason_detail: Mapped[str | None] = mapped_column(String(100), nullable=True)


class CustomerCaseReasonChangeModel(Base):
    """Tabela `customer_case_reason_changes` - historia powodu sprawy."""

    __tablename__ = "customer_case_reason_changes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("customer_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    previous_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(nullable=False)
