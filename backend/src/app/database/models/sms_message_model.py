"""Model ORM tabeli historii wiadomości SMS."""

from __future__ import annotations

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class SmsMessageModel(Base, TimestampMixin):
    """
    Tabela `sms_messages`.

    Historia wszystkich prób wysyłki SMS do klientów. Kolumna `status`
    (SENT/FAILED/SKIPPED_NO_PHONE) pozwala odróżnić skuteczne wysyłki od
    prób nieudanych i pominiętych. Indeks (order_external_id, message_type)
    przyspiesza sprawdzenie, czy dany SMS już poszedł.
    """

    __tablename__ = "sms_messages"
    __table_args__ = (
        Index("ix_sms_messages_order_type", "order_external_id", "message_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    message_type: Mapped[str] = mapped_column(String(50), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
