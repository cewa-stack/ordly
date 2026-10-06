"""przetworzone maile InPost o paczkach od hurtowni

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-06 00:00:00

Pozycja z Notion [FEAT-MAIL] „Jednorazowe powiadomienie o mailu InPost
dotyczącym paczki od F.H.P. MAIK-POL”. Tabela `processed_parcel_mails`
zapamiętuje każdy rozpatrzony mail „InPost - Potwierdzenie nadania
przesyłki” (Message-ID, data, nadawca, temat, wynik, numer paczki,
hurtownia, czy był alert), żeby ten sam mail nigdy nie dał drugiego
alertu.

Nowa tabela, istniejących nie rusza - downgrade usuwa tylko ją.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Tworzy tabelę processed_parcel_mails."""
    op.create_table(
        "processed_parcel_mails",
        sa.Column("message_id", sa.String(length=500), primary_key=True),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("sender", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("tracking_number", sa.String(length=40), nullable=True),
        sa.Column("wholesaler", sa.String(length=120), nullable=True),
        sa.Column("alerted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_processed_parcel_mails_received_at", "processed_parcel_mails", ["received_at"]
    )


def downgrade() -> None:
    """Usuwa tabelę processed_parcel_mails."""
    op.drop_index("ix_processed_parcel_mails_received_at", "processed_parcel_mails")
    op.drop_table("processed_parcel_mails")
