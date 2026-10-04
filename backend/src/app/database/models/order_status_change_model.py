"""Model ORM historii zmian statusu aplikacyjnego zamówienia."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class OrderStatusChangeModel(Base):
    """
    Tabela `order_status_changes` - jeden wiersz na każdą ręczną zmianę
    statusu aplikacyjnego (albo przywrócenie statusu z Allegro).

    Statusy są zapisane jako status WIDOCZNY dla użytkownika przed i po
    zmianie (NULL = "Brak danych"). Tabela nie trzyma danych kupującego.
    """

    __tablename__ = "order_status_changes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    marketplace: Mapped[str] = mapped_column(String(50), nullable=False)
    order_external_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    previous_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(nullable=False)
