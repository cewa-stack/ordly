"""zdarzenia dla ORDLy Control Hub

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-04 00:00:00

Control Hub (ESP32 z ekranem i diodami) pokazuje zdarzenia z ORDLY,
dopóki ktoś ich nie potwierdzi przyciskiem OK albo sprawa nie rozwiąże
się w aplikacji. Hub nic nie pamięta po restarcie, więc listę aktywnych
zdarzeń trzyma ORDLY. Nowa tabela, istniejących nie rusza - downgrade
usuwa tylko ją.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Tworzy tabelę hub_events."""
    op.create_table(
        "hub_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_key", sa.String(length=200), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("priority", sa.String(length=10), nullable=False),
        sa.Column("data_json", sa.Text(), nullable=False),
        sa.Column("acked_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolve_reason", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source_key", name="uq_hub_events_source_key"),
    )


def downgrade() -> None:
    """Usuwa tabelę hub_events."""
    op.drop_table("hub_events")
