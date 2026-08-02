"""Model ORM tabeli ustawień runtime (klucz-wartość)."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class SettingsModel(Base, TimestampMixin):
    """
    Tabela `settings`.

    Ustawienia modyfikowalne w runtime (np. przez komendy Telegram),
    w odróżnieniu od konfiguracji z .env, która wymaga restartu
    aplikacji, aby zmiana zaczęła obowiązywać.
    """

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(nullable=False)
