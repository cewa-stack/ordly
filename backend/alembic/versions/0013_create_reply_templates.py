"""szablony odpowiedzi w dyskusjach

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-22 00:00:00

Szablony odpowiedzi żyły dotąd na sztywno w kodzie desktopu, a telefon
nie miał ich wcale. Teraz są w bazie: te same na obu aplikacjach,
edytowalne w Ustawieniach desktopu.

Migracja wstawia cztery dotychczasowe szablony (bez zmiany treści, żeby
nic, do czego ręka przywykła, nie zniknęło) i jeden nowy z numerem
przesyłki - znacznik `{numer_przesylki}` podstawia aplikacja z danych
zamówienia, którego dotyczy dyskusja.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEFAULTS: list[tuple[str, str]] = [
    (
        "Potwierdzenie zgłoszenia",
        "Dzień dobry,\n\ndziękuję za zgłoszenie. Sprawdzam sprawę i wracam z odpowiedzią "
        "najpóźniej jutro do południa.\n\nPozdrawiam",
    ),
    (
        "Wysyłka w toku",
        "Dzień dobry,\n\npaczka jest już spakowana i trafi do kuriera dzisiaj. Numer przesyłki "
        "wyślę, gdy tylko go otrzymam.\n\nPozdrawiam",
    ),
    (
        "Wysłane — numer przesyłki",
        "Dzień dobry,\n\npaczka jest już w drodze. Numer przesyłki: {numer_przesylki}.\n\n"
        "Dziękuję za zakup i pozdrawiam",
    ),
    (
        "Prośba o zdjęcia",
        "Dzień dobry,\n\nżeby szybciej rozwiązać sprawę, proszę o 2-3 zdjęcia produktu "
        "i opakowania. Na tej podstawie od razu zaproponuję rozwiązanie.\n\nPozdrawiam",
    ),
    (
        "Zwrot przyjęty",
        "Dzień dobry,\n\nzwrot przyjęty. Zwrot środków uruchamiam po odbiorze przesyłki - "
        "księgowanie zajmuje zwykle 2-3 dni robocze.\n\nPozdrawiam",
    ),
]


def upgrade() -> None:
    """Tworzy tabelę reply_templates i wstawia szablony startowe."""
    table = op.create_table(
        "reply_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(length=80), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    # Baza trzyma naiwny UTC (zob. `utc_now`), więc bez `tzinfo`.
    now = datetime.now(UTC).replace(tzinfo=None)
    op.bulk_insert(
        table,
        [
            {"title": title, "body": body, "position": index, "created_at": now, "updated_at": now}
            for index, (title, body) in enumerate(_DEFAULTS, start=1)
        ],
    )


def downgrade() -> None:
    """Usuwa tabelę reply_templates (razem z własnymi szablonami)."""
    op.drop_table("reply_templates")
