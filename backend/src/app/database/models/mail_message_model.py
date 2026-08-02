"""Model ORM tabeli wykrytych maili od marketplace (Allegro/OLX)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class MailMessageModel(Base, TimestampMixin):
    """
    Tabela `mail_messages`.

    `message_id` (nagłówek Message-ID) jest kluczem głównym - globalnie
    unikalny z natury, więc nie potrzeba osobnego autoincrement id ani
    unique constraint jak w innych tabelach synchronizowanych.
    """

    __tablename__ = "mail_messages"

    message_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    sender: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    received_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    body_preview: Mapped[str] = mapped_column(String(600), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
