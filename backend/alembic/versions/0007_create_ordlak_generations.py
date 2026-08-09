"""create ordlak_generations table

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-09 00:00:00

Dodaje tabelę ordlak_generations - historia ofert wygenerowanych przez
Ordlaka (moduł AI do wystawiania na Allegro). Zdjęcia wysłane do modelu
NIE są przechowywane, tylko ich liczba (patrz bot_ordlak/bot.md, sekcja 3).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Tworzy tabelę ordlak_generations."""
    op.create_table(
        "ordlak_generations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_note", sa.Text(), nullable=False),
        sa.Column("condition", sa.String(length=20), nullable=False),
        sa.Column("purchase_cost", sa.Float(), nullable=False),
        sa.Column("inbound_shipping_cost", sa.Float(), nullable=False),
        sa.Column("buyer_shipping_cost", sa.Float(), nullable=False),
        sa.Column("commission_percent", sa.Float(), nullable=False),
        sa.Column("target_margin_percent", sa.Float(), nullable=False),
        sa.Column("photo_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generated_title", sa.String(length=200), nullable=False),
        sa.Column("generated_description_html", sa.Text(), nullable=False),
        sa.Column("ai_condition_notes", sa.Text(), nullable=True),
        sa.Column("suggested_price", sa.Float(), nullable=False),
        sa.Column("final_title", sa.String(length=200), nullable=True),
        sa.Column("final_description_html", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    """Usuwa tabelę ordlak_generations."""
    op.drop_table("ordlak_generations")
