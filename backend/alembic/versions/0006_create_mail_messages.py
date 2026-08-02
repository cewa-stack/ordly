"""create mail_messages table

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-01 00:00:00

Dodaje tabelę mail_messages - cache metadanych maili od marketplace
(Allegro/OLX) wykrytych przez IMAP watcher (etap "Skrzynka"). Pełna
treść maila nie jest cache'owana - tylko podgląd (body_preview).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Tworzy tabelę mail_messages."""
    op.create_table(
        "mail_messages",
        sa.Column("message_id", sa.String(length=255), primary_key=True),
        sa.Column("sender", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("body_preview", sa.String(length=600), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_mail_messages_received_at", "mail_messages", ["received_at"])
    op.create_index("ix_mail_messages_source", "mail_messages", ["source"])


def downgrade() -> None:
    """Usuwa tabelę mail_messages."""
    op.drop_index("ix_mail_messages_source", table_name="mail_messages")
    op.drop_index("ix_mail_messages_received_at", table_name="mail_messages")
    op.drop_table("mail_messages")
