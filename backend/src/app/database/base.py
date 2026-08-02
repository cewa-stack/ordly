"""
Deklaratywna baza SQLAlchemy dla wszystkich modeli ORM.

Wszystkie modele w database/models/ muszą dziedziczyć po Base
zdefiniowanej tutaj - to gwarantuje, że Alembic (autogenerate)
widzi wszystkie tabele w jednym miejscu.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.utils.time import utc_now


class Base(DeclarativeBase):
    """Bazowa klasa deklaratywna dla wszystkich modeli ORM aplikacji."""

    pass


class TimestampMixin:
    """
    Mixin dodający kolumny `created_at` i `updated_at`.

    Współdzielony przez wszystkie modele, aby uniknąć powielania
    identycznych definicji kolumn (zasada DRY).
    """

    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=utc_now, onupdate=utc_now, nullable=False
    )
