"""create initial tables

Revision ID: 0001
Revises:
Create Date: 2026-07-18 00:00:00

Ta migracja tworzy wszystkie sześć tabel wymaganych przez projekt:
orders, products, shipments, events, settings, tokens.

UWAGA: to jest szablon startowy. Zalecane jest wygenerowanie
właściwej migracji poleceniem:
    uv run alembic revision --autogenerate -m "create initial tables"
i porównanie wyniku z tym plikiem, ponieważ autogenerate lepiej
odzwierciedli faktyczne typy kolumn Twojej wersji SQLAlchemy.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Tworzy tabele: orders, products, shipments, events, settings, tokens."""
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("marketplace", sa.String(length=50), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=False),
        sa.Column("buyer_login", sa.String(length=255), nullable=False),
        sa.Column("buyer_email", sa.String(length=255), nullable=True),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="PLN"),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("order_date", sa.DateTime(), nullable=False),
        sa.Column("notified_at", sa.DateTime(), nullable=True),
        sa.Column("raw_payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("marketplace", "external_id", name="uq_order_marketplace_external_id"),
    )
    op.create_index("ix_orders_marketplace", "orders", ["marketplace"])
    op.create_index("ix_orders_external_id", "orders", ["external_id"])
    op.create_index("ix_orders_notified_at", "orders", ["notified_at"])

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_product_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_products_order_id", "products", ["order_id"])

    op.create_table(
        "shipments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("carrier", sa.String(length=100), nullable=True),
        sa.Column("tracking_number", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=100), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("level", sa.String(length=20), nullable=False, server_default="INFO"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_events_event_type", "events", ["event_type"])

    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("marketplace", sa.String(length=50), nullable=False, unique=True),
        sa.Column("encrypted_access_token", sa.Text(), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_tokens_marketplace", "tokens", ["marketplace"])


def downgrade() -> None:
    """Usuwa wszystkie utworzone tabele (odwrotna kolejność do FK)."""
    op.drop_table("tokens")
    op.drop_table("settings")
    op.drop_table("events")
    op.drop_table("shipments")
    op.drop_table("products")
    op.drop_table("orders")
