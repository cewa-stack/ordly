"""create marketplace_offers

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-06 00:00:00

Lokalny katalog asortymentu wystawionego na marketplace.

Do tej pory jedynym źródłem identyfikatorów ofert była historia
zamówień, więc recepturę dało się przypisać dopiero PO pierwszej
sprzedaży - a ta sprzedaż z definicji przechodziła obok magazynu.
Katalog odwraca kolejność: oferty są znane, zanim cokolwiek się sprzeda.

Tabela jest w całości odtwarzalna z API marketplace (pełny refresh przy
każdej synchronizacji), dlatego downgrade po prostu ją kasuje.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Tworzy tabelę katalogu ofert marketplace."""
    op.create_table(
        "marketplace_offers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("marketplace", sa.String(length=50), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("signature", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="ACTIVE"),
        sa.Column("available_stock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sold_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("price", sa.Numeric(), nullable=True),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("marketplace", "external_id", name="uq_marketplace_offer"),
    )
    op.create_index(
        "ix_marketplace_offers_marketplace", "marketplace_offers", ["marketplace"]
    )
    op.create_index(
        "ix_marketplace_offers_external_id", "marketplace_offers", ["external_id"]
    )
    op.create_index("ix_marketplace_offers_signature", "marketplace_offers", ["signature"])


def downgrade() -> None:
    """Usuwa tabelę katalogu ofert."""
    op.drop_index("ix_marketplace_offers_signature", table_name="marketplace_offers")
    op.drop_index("ix_marketplace_offers_external_id", table_name="marketplace_offers")
    op.drop_index("ix_marketplace_offers_marketplace", table_name="marketplace_offers")
    op.drop_table("marketplace_offers")
