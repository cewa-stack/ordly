"""split allegro_lokalnie mail source

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-26 00:00:00

Rozdziela kanał Allegro Lokalnie od Allegro.pl w tabeli `mail_messages`.

Nie zmienia SCHEMATU - kolumna `source` to zwykły tekst - tylko poprawia
DANE już zapisane. Powód: `classify_sender` sprawdzało wcześniej podciąg
"allegro" przed "allegrolokalnie", więc każde powiadomienie z Allegro
Lokalnie zostało zapisane jako "allegro". Bez tej poprawki stare maile
zostałyby na zawsze pod filtrem Allegro.pl, a użytkownik widziałby dwa
różne serwisy pod jedną etykietą.

Migracja jest idempotentna i odwracalna: `downgrade` scala kanał
z powrotem w "allegro", czyli dokładnie w stan sprzed zmiany.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Przenosi już zapisane maile z allegrolokalnie.pl do własnego kanału."""
    op.execute(
        sa.text(
            "UPDATE mail_messages SET source = 'allegro_lokalnie' "
            "WHERE source = 'allegro' AND LOWER(sender) LIKE '%allegrolokalnie%'"
        )
    )


def downgrade() -> None:
    """Scala kanał z powrotem w 'allegro' - stan sprzed rozdzielenia."""
    op.execute(
        sa.text("UPDATE mail_messages SET source = 'allegro' WHERE source = 'allegro_lokalnie'")
    )
