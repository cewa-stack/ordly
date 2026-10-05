"""Model ORM tabeli zdarzeń ORDLy Control Hub."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class HubEventModel(Base, TimestampMixin):
    """
    Tabela `hub_events`.

    Aktywne zdarzenie = `acked_at` i `resolved_at` puste. Wiersze
    zamkniętych zdarzeń zostają jako historia (kiedy i czym zamknięto) -
    są małe i przybywa ich kilkanaście dziennie.
    """

    __tablename__ = "hub_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_key: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    priority: Mapped[str] = mapped_column(String(10), nullable=False)
    data_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    acked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    resolve_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
