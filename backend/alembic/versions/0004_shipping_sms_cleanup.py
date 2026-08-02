"""shipping status, sms messages and telegram cleanup

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-20 12:00:00

Dodaje elementy potrzebne dla trzech funkcji:
- kolumny orders.fulfillment_status i orders.buyer_phone (etap realizacji
  i telefon klienta) - podstawa przypomnienia o wysyłce, nocnego czyszczenia
  czatu oraz SMS o pakowaniu,
- tabela sms_messages (historia i jednorazowość SMS do klienta),
- tabela telegram_messages (rejestr wiadomości bota do nocnego czyszczenia).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Dodaje kolumny zamówień oraz tabele sms_messages i telegram_messages."""
    op.add_column(
        "orders",
        sa.Column("buyer_phone", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("fulfillment_status", sa.String(length=50), nullable=True),
    )
    op.create_index("ix_orders_fulfillment_status", "orders", ["fulfillment_status"])

    op.create_table(
        "sms_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_external_id", sa.String(length=100), nullable=False),
        sa.Column("message_type", sa.String(length=50), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("detail", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_sms_messages_order_type",
        "sms_messages",
        ["order_external_id", "message_type"],
    )

    op.create_table(
        "telegram_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_telegram_messages_chat_id", "telegram_messages", ["chat_id"])


def downgrade() -> None:
    """Usuwa dodane tabele i kolumny (odwrotna kolejność)."""
    op.drop_table("telegram_messages")
    op.drop_index("ix_sms_messages_order_type", table_name="sms_messages")
    op.drop_table("sms_messages")
    op.drop_index("ix_orders_fulfillment_status", table_name="orders")
    op.drop_column("orders", "fulfillment_status")
    op.drop_column("orders", "buyer_phone")
