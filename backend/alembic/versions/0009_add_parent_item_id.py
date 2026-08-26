"""add parent_item_id to inventory_items

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-26 12:00:00

Dodaje relację produkt główny -> podprodukty w obrębie samego magazynu.

Po co osobna relacja, skoro istnieje już `offer_links`: tamta mapuje
OFERTĘ marketplace na składniki i trzeba ją powtórzyć przy każdej nowej
ofercie. Ta jest własnością SAMEGO PRODUKTU - butelka zawsze idzie
w parze z nakrętką i kroplomierzem, niezależnie od tego, przez którą
ofertę i który serwis się sprzedała.

`ondelete="SET NULL"` celowo: usunięcie produktu głównego nie kasuje
podproduktów, tylko je odwiązuje (wracają na listę jako samodzielne).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Dodaje kolumnę wskazującą produkt główny oraz indeks po niej.

    Surowy `ALTER TABLE` zamiast `op.add_column()`: alembic próbowałby
    dopiąć klucz obcy osobnym `ALTER`, a tego SQLite nie umie
    (NotImplementedError z dialektu). Alternatywa - `batch_alter_table` -
    przepisuje całą tabelę przez kopiuj-i-przenieś, czego na działającej
    bazie z historią magazynu nie warto robić dla jednej kolumny.
    SQLite dopuszcza `REFERENCES` w samej definicji dokładanej kolumny,
    o ile jej wartość domyślna to NULL - i dokładnie tak tu jest.
    """
    op.execute(
        sa.text(
            "ALTER TABLE inventory_items ADD COLUMN parent_item_id INTEGER "
            "REFERENCES inventory_items(id) ON DELETE SET NULL"
        )
    )
    op.create_index(
        "ix_inventory_items_parent_item_id", "inventory_items", ["parent_item_id"]
    )


def downgrade() -> None:
    """
    Usuwa kolumnę i indeks.

    Kolejność ma znaczenie: SQLite odmawia usunięcia kolumny, po której
    istnieje indeks, więc indeks leci pierwszy.
    """
    op.drop_index("ix_inventory_items_parent_item_id", table_name="inventory_items")
    op.drop_column("inventory_items", "parent_item_id")
