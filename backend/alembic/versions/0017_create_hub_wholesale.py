"""zamówienia do hurtowni z ORDLy Control Hub

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-06 00:00:00

Control Hub dostaje ekran "Zamów w hurtowni". Hurtownie i szablony maili
żyją w aplikacji desktopowej; desktop wysyła ich kopię na Pi, a ORDLY
składa i wysyła mail na prośbę Huba.

- `hub_wholesale_catalog` - jeden wiersz z kopią hurtowni i szablonów,
- `hub_wholesale_orders` - każda próba wysyłki z Huba (unikalny
  `request_id` chroni przed podwójnym mailem).

Nowe tabele, istniejących nie rusza - downgrade usuwa tylko je.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Tworzy tabele hub_wholesale_catalog i hub_wholesale_orders."""
    op.create_table(
        "hub_wholesale_catalog",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "hub_wholesale_orders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("wholesaler_id", sa.String(length=64), nullable=False),
        sa.Column("wholesaler_name", sa.String(length=200), nullable=False),
        sa.Column("to_email", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("items_summary", sa.Text(), nullable=False),
        sa.Column("items_key", sa.String(length=64), nullable=False),
        sa.Column("test_mode", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("request_id", name="uq_hub_wholesale_orders_request_id"),
    )
    op.create_index(
        "ix_hub_wholesale_orders_wholesaler_id", "hub_wholesale_orders", ["wholesaler_id"]
    )


def downgrade() -> None:
    """Usuwa obie tabele."""
    op.drop_index("ix_hub_wholesale_orders_wholesaler_id", table_name="hub_wholesale_orders")
    op.drop_table("hub_wholesale_orders")
    op.drop_table("hub_wholesale_catalog")
