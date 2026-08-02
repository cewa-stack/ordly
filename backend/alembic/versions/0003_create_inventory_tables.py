"""create inventory tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-19 12:00:00

Dodaje tabele Inventory Management System oraz automatycznej
synchronizacji stanów: inventory_items (centralny magazyn),
inventory_movements (historia zmian), offer_links (mapowanie ofert
marketplace na składniki magazynowe, w tym zestawy) i stock_syncs
(znaczniki chroniące przed podwójnym odjęciem stanów).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Tworzy tabele: inventory_items, inventory_movements, offer_links, stock_syncs."""
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("sku", sa.String(length=100), nullable=False, unique=True),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("ean", sa.String(length=20), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("stock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("min_stock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_stock", sa.Integer(), nullable=True),
        sa.Column("purchase_cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("sale_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("location", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_inventory_items_sku", "inventory_items", ["sku"], unique=True)

    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("inventory_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("change", sa.Integer(), nullable=False),
        sa.Column("stock_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_inventory_movements_item_id", "inventory_movements", ["item_id"]
    )
    op.create_index("ix_inventory_movements_source", "inventory_movements", ["source"])

    op.create_table(
        "offer_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("marketplace", sa.String(length=50), nullable=False),
        sa.Column("external_product_id", sa.String(length=100), nullable=False),
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("inventory_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "marketplace", "external_product_id", "item_id", name="uq_offer_link"
        ),
    )
    op.create_index(
        "ix_offer_links_external_product_id", "offer_links", ["external_product_id"]
    )
    op.create_index("ix_offer_links_item_id", "offer_links", ["item_id"])

    op.create_table(
        "stock_syncs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("marketplace", sa.String(length=50), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=False),
        sa.Column("operation", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "marketplace", "reference", "operation", name="uq_stock_sync_operation"
        ),
    )
    op.create_index("ix_stock_syncs_reference", "stock_syncs", ["reference"])


def downgrade() -> None:
    """Usuwa tabele magazynu (odwrotna kolejność do FK)."""
    op.drop_table("stock_syncs")
    op.drop_table("offer_links")
    op.drop_table("inventory_movements")
    op.drop_table("inventory_items")
