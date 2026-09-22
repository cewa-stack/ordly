"""Model ORM tabeli szablonów odpowiedzi."""

from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class ReplyTemplateModel(Base, TimestampMixin):
    """
    Tabela `reply_templates`.

    `position` ustala kolejność na liście - nowy szablon ląduje na końcu,
    żeby dopisanie własnego nie przestawiało tych, do których ręka już
    przywykła.
    """

    __tablename__ = "reply_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
