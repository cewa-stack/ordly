"""Modele ORM zapisanych rozmów z asystentem Ordlaka."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class OrdlakConversationModel(Base, TimestampMixin):
    """
    Tabela `ordlak_conversations` - wątek rozmowy.

    `updated_at` z `TimestampMixin` jest tu polem SORTUJĄCYM listę rozmów
    (ostatnio używane na górze), a nie tylko metadaną - dlatego serwis
    dotyka wątku przy każdej dopisanej wiadomości.
    """

    __tablename__ = "ordlak_conversations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)


class OrdlakMessageModel(Base, TimestampMixin):
    """
    Tabela `ordlak_messages` - pojedyncze wypowiedzi w wątku.

    `used_tools` leży jako lista nazw rozdzielonych przecinkami, nie jako
    osobna tabela: to ślad diagnostyczny do wyświetlenia pod odpowiedzią,
    po którym nigdy nie będziemy filtrować ani go łączyć.

    `ondelete="CASCADE"` - usunięcie wątku zabiera jego wiadomości.
    Osierocona wypowiedź bez rozmowy nie znaczy nic.
    """

    __tablename__ = "ordlak_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("ordlak_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    used_tools: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    sent_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
