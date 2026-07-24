"""create push_subscriptions table

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-24 09:00:00

Dodaje tabelę push_subscriptions - przechowuje subskrypcje Web Push
(RFC 8030) zgłoszone przez TOOM Mobile uruchomiony jako PWA (drugi,
opcjonalny kanał powiadomień obok bota Telegram).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Tworzy tabelę push_subscriptions."""
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("endpoint", sa.String(length=1000), nullable=False),
        sa.Column("p256dh", sa.String(length=255), nullable=False),
        sa.Column("auth", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_push_subscriptions_endpoint",
        "push_subscriptions",
        ["endpoint"],
        unique=True,
    )


def downgrade() -> None:
    """Usuwa tabelę push_subscriptions."""
    op.drop_index("ix_push_subscriptions_endpoint", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
