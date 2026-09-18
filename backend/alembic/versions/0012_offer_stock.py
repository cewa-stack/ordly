"""magazyn oparty o oferty zamiast produktów SKU

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-18 00:00:00

Magazyn przestaje być osobnym rejestrem produktów SKU z recepturami
i automatycznym odejmowaniem stanów. Zostaje jedna lista: oferty
pobrane z marketplace, a przy każdej z nich ręcznie wpisana ilość.

DLACZEGO TO KASUJE DANE. Automatyczne odejmowanie dawało wiarygodne
stany tylko wtedy, gdy KAŻDA oferta miała poprawną recepturę - oferta
bez receptury sprzedawała się obok magazynu, a błędna odejmowała nie
ten towar. Liczby w `inventory_items` były więc mieszaniną stanów
prawdziwych i takich, których nikt nie pilnował, i nie da się ich
automatycznie przypisać do ofert. Przeniesienie ich do
`quantity_on_hand` przepisałoby te same nieufne liczby w nowe miejsce,
więc ilości startują puste (NULL = „nie wpisano") i uzupełnia się je
ręcznie z desktopu.

Przed uruchomieniem na Pi zrób kopię pliku bazy - downgrade odtwarza
puste tabele, nie ich zawartość.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Dokłada ilość i historię do ofert, kasuje magazyn SKU."""
    op.add_column(
        "marketplace_offers", sa.Column("quantity_on_hand", sa.Integer(), nullable=True)
    )

    op.create_table(
        "offer_stock_movements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("change", sa.Integer(), nullable=True),
        sa.Column("quantity_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["offer_id"], ["marketplace_offers.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_offer_stock_movements_offer_id", "offer_stock_movements", ["offer_id"]
    )

    # Kolejność ma znaczenie: obie tabele wiszą kluczem obcym na
    # `inventory_items`, więc rodzic schodzi na końcu.
    op.drop_table("inventory_movements")
    op.drop_table("offer_links")
    op.drop_table("stock_syncs")
    op.drop_table("inventory_items")


def downgrade() -> None:
    """Odtwarza PUSTE tabele magazynu SKU i zdejmuje ilości z ofert."""
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
        sa.Column(
            "parent_item_id",
            sa.Integer(),
            sa.ForeignKey("inventory_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_inventory_items_sku", "inventory_items", ["sku"], unique=True)
    op.create_index(
        "ix_inventory_items_parent_item_id", "inventory_items", ["parent_item_id"]
    )

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
    op.create_index("ix_inventory_movements_item_id", "inventory_movements", ["item_id"])
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

    op.drop_index("ix_offer_stock_movements_offer_id", table_name="offer_stock_movements")
    op.drop_table("offer_stock_movements")
    op.drop_column("marketplace_offers", "quantity_on_hand")
