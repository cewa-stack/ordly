"""status aplikacyjny zamówienia ustawiany ręcznie

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-04 00:00:00

Pozycja z Notion "Brak ręcznej zmiany statusu zamówienia wyłącznie
w aplikacji". Zamówienie dostaje status ustawiany ręcznie w ORDLY
(Nowe / W realizacji / Zrealizowane / Anulowane), niezależny od Allegro:

- `orders.app_status` - ręczny status (NULL = brak ręcznej zmiany,
  status liczony z danych Allegro - tak jak dotąd);
- `orders.app_status_basis` - status wynikający z Allegro w chwili
  ręcznej zmiany (reguła priorytetu, app/domain/order_status.py);
- `orders.app_status_changed_at` - kiedy zmieniono ręcznie;
- `order_status_changes` - historia ręcznych zmian.

Migracja tylko dokłada kolumny i tabelę - istniejące zamówienia mają
NULL, więc zachowują się dokładnie jak przed wdrożeniem.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Dokłada kolumny ręcznego statusu i tabelę historii zmian."""
    op.add_column("orders", sa.Column("app_status", sa.String(length=20), nullable=True))
    op.add_column(
        "orders", sa.Column("app_status_basis", sa.String(length=20), nullable=True)
    )
    op.add_column("orders", sa.Column("app_status_changed_at", sa.DateTime(), nullable=True))
    op.create_index("ix_orders_app_status", "orders", ["app_status"])

    op.create_table(
        "order_status_changes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("marketplace", sa.String(length=50), nullable=False),
        sa.Column("order_external_id", sa.String(length=100), nullable=False),
        sa.Column("previous_status", sa.String(length=20), nullable=True),
        sa.Column("new_status", sa.String(length=20), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_order_status_changes_order_external_id",
        "order_status_changes",
        ["order_external_id"],
    )


def downgrade() -> None:
    """Usuwa ręczne statusy i ich historię (zamówienia wracają do statusu z Allegro)."""
    op.drop_index("ix_order_status_changes_order_external_id", "order_status_changes")
    op.drop_table("order_status_changes")
    op.drop_index("ix_orders_app_status", "orders")
    op.drop_column("orders", "app_status_changed_at")
    op.drop_column("orders", "app_status_basis")
    op.drop_column("orders", "app_status")
