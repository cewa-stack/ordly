"""Model ORM tabeli zdarzeń (audit log Event Busa)."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class EventModel(Base, TimestampMixin):
    """
    Tabela `events`.

    Przechowuje historię wszystkich zdarzeń emitowanych przez
    Event Bus (OrderCreated, SyncFinished itd.) - służy do
    debugowania i komendy /logs w Telegramie.
    """

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload_json: Mapped[str | None] = mapped_column(nullable=True)
    level: Mapped[str] = mapped_column(String(20), default="INFO", nullable=False)
