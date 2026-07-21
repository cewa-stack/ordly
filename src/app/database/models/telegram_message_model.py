"""Model ORM tabeli wysłanych wiadomości Telegram (do nocnego czyszczenia)."""

from __future__ import annotations

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class TelegramMessageModel(Base, TimestampMixin):
    """
    Tabela `telegram_messages`.

    Rejestr identyfikatorów wiadomości wysłanych przez bota TOOM na czat
    administratora. Pozwala nocnemu zadaniu czyszczącemu (02:00) usunąć
    wszystkie wcześniejsze wiadomości bota, aby rano na czacie widoczne
    były wyłącznie ponownie opublikowane, aktualne zamówienia.
    """

    __tablename__ = "telegram_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
