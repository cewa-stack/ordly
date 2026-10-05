"""Modele ORM zamówień do hurtowni z ORDLy Control Hub."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class HubWholesaleCatalogModel(Base, TimestampMixin):
    """
    Tabela `hub_wholesale_catalog` - jeden wiersz (id = 1): kopia hurtowni
    i szablonów maili z aplikacji desktopowej, tak jak desktop ją przysłał.
    """

    __tablename__ = "hub_wholesale_catalog"

    id: Mapped[int] = mapped_column(primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)


class HubWholesaleOrderModel(Base, TimestampMixin):
    """
    Tabela `hub_wholesale_orders` - każda próba wysyłki z Huba.

    `request_id` (nadany przez Hub) jest unikalny: ta sama prośba
    powtórzona po zerwanym połączeniu nie wyśle drugiego maila.
    `status`: `sending` (zapisane przed SMTP), `sent`, `failed`.
    """

    __tablename__ = "hub_wholesale_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    wholesaler_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    wholesaler_name: Mapped[str] = mapped_column(String(200), nullable=False)
    to_email: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    items_summary: Mapped[str] = mapped_column(Text, nullable=False)
    items_key: Mapped[str] = mapped_column(String(64), nullable=False)
    test_mode: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
