"""create ordlak_conversations and ordlak_messages

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-06 00:00:00

Dodaje trwałą historię rozmów z asystentem Ordlaka. Do tej pory wątek
żył wyłącznie w pamięci aplikacji desktopowej i ginął przy restarcie -
raport sprzed godziny nie dawał się odtworzyć.

`used_tools` trafia do kolumny tekstowej (nazwy po przecinku), a nie do
osobnej tabeli: to ślad diagnostyczny do wyświetlenia pod odpowiedzią,
po którym nigdy nie będziemy filtrować ani go łączyć.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Tworzy tabele wątków i wiadomości."""
    op.create_table(
        "ordlak_conversations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "ordlak_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("ordlak_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("used_tools", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_ordlak_messages_conversation_id", "ordlak_messages", ["conversation_id"]
    )
    op.create_index("ix_ordlak_messages_sent_at", "ordlak_messages", ["sent_at"])


def downgrade() -> None:
    """Usuwa obie tabele. Kolejność odwrotna do tworzenia (klucz obcy)."""
    op.drop_index("ix_ordlak_messages_sent_at", table_name="ordlak_messages")
    op.drop_index("ix_ordlak_messages_conversation_id", table_name="ordlak_messages")
    op.drop_table("ordlak_messages")
    op.drop_table("ordlak_conversations")
