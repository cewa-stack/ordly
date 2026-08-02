"""create customer_returns table

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-19 00:00:00

Dodaje tabelę customer_returns przechowującą wykryte zwroty klientów -
unique constraint (marketplace, external_id) gwarantuje, że powiadomienie
o danym zwrocie zostanie wysłane tylko raz.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Tworzy tabelę customer_returns."""
    op.create_table(
        "customer_returns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("marketplace", sa.String(length=50), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=False),
        sa.Column("order_external_id", sa.String(length=100), nullable=False),
        sa.Column("buyer_login", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("products_summary", sa.String(length=1000), nullable=False),
        sa.Column("return_date", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "marketplace", "external_id", name="uq_return_marketplace_external_id"
        ),
    )
    op.create_index(
        "ix_customer_returns_marketplace", "customer_returns", ["marketplace"]
    )
    op.create_index(
        "ix_customer_returns_external_id", "customer_returns", ["external_id"]
    )
    op.create_index(
        "ix_customer_returns_order_external_id",
        "customer_returns",
        ["order_external_id"],
    )


def downgrade() -> None:
    """Usuwa tabelę customer_returns."""
    op.drop_table("customer_returns")
