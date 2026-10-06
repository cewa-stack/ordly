"""Model ORM przetworzonych maili InPost o paczkach od hurtowni ([FEAT-MAIL])."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class ProcessedParcelMailModel(Base, TimestampMixin):
    """
    Tabela `processed_parcel_mails` - każdy mail „InPost - Potwierdzenie
    nadania przesyłki”, który ORDLY już rozpatrzył, z wynikiem.

    Klucz główny to Message-ID: ponowne pobranie tego samego maila nie
    tworzy drugiego alertu (W8, W9). Zapisywane są też maile BEZ alertu
    (inny hurtownik), żeby nie dociągać ich treści w każdym cyklu.
    Maile InPost nie trafiają do `mail_messages` (zakładka Poczta) -
    decyzja M1-a.
    """

    __tablename__ = "processed_parcel_mails"

    message_id: Mapped[str] = mapped_column(String(500), primary_key=True)
    received_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    sender: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    #: Wynik rozpoznania (`app/infrastructure/mail/inpost.py`, OUTCOME_*).
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    tracking_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    wholesaler: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #: Czy z tego maila wyszedł alert (Hub + push).
    alerted: Mapped[bool] = mapped_column(nullable=False, default=False)
