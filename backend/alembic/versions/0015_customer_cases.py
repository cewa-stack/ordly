"""rejestr anulowań i zwrotów pieniędzy

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-05 00:00:00

Pozycje z Notion "Brak automatycznego zbierania danych klientów po
anulowaniu zamówienia lub zwrocie pieniędzy" i "Brak miejsca i
jednolitego formatu dla danych klientów po zwrotach".

- `customer_cases` - jeden rekord na zamówienie (kanał + numer):
  rodzaj (anulowanie / zwrot pieniędzy / oba), daty, powód, status obsługi,
  źródło, login Allegro. BEZ telefonu, e-maila i imienia i nazwiska
  (decyzja użytkownika D7).
- `customer_case_reason_changes` - historia powodu.

Uzupełnienie wsteczne: zamówienia już anulowane i zwroty z oddanymi
pieniędzmi dostają rekord ze źródłem "Dane sprzed wdrożenia". Daty
anulowania i zwrotu pieniędzy są dla nich nieznane (NULL =
"nieuzupełnione"), powód też - uzupełnia się go ręcznie na desktopie.
Jako historia trafiają od razu do statusu obsługi "Zakończony", żeby nie
zalały zakładki "Zgłoszony"; można je przenieść ręcznie.
Downgrade usuwa obie tabele razem z ręcznie wpisanymi powodami.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REFUNDED_RETURN_STATUSES = (
    "FINISHED",
    "FINISHED_APT",
    "COMMISSION_REFUND_CLAIMED",
    "COMMISSION_REFUNDED",
)


def upgrade() -> None:
    """Tworzy rejestr i uzupełnia go danymi sprzed wdrożenia."""
    op.create_table(
        "customer_cases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("marketplace", sa.String(length=50), nullable=False),
        sa.Column("order_external_id", sa.String(length=100), nullable=False),
        sa.Column("allegro_order_id", sa.String(length=100), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("handling_status", sa.String(length=20), nullable=False),
        sa.Column("buyer_login", sa.String(length=255), nullable=True),
        sa.Column("order_date", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("refunded_at", sa.DateTime(), nullable=True),
        sa.Column("reason", sa.String(length=30), nullable=True),
        sa.Column("reason_detail", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "marketplace", "order_external_id", name="uq_customer_case_marketplace_order"
        ),
    )
    for column in ("order_external_id", "kind", "source", "handling_status", "reason"):
        op.create_index(f"ix_customer_cases_{column}", "customer_cases", [column])

    op.create_table(
        "customer_case_reason_changes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("previous_reason", sa.String(length=30), nullable=True),
        sa.Column("new_reason", sa.String(length=30), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["customer_cases.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_customer_case_reason_changes_case_id", "customer_case_reason_changes", ["case_id"]
    )

    _backfill()


def _backfill() -> None:
    """Rekordy dla anulowań i zwrotów pieniędzy sprzed wdrożenia."""
    bind = op.get_bind()
    now = datetime.now(UTC).replace(tzinfo=None)
    login = (
        "CASE WHEN TRIM(COALESCE({col}, '')) IN ('', 'nieznany') THEN NULL ELSE {col} END"
    )
    bind.execute(
        sa.text(
            "INSERT INTO customer_cases (marketplace, order_external_id, allegro_order_id, "
            "kind, source, handling_status, buyer_login, order_date, created_at, updated_at) "
            "SELECT marketplace, external_id, "
            "CASE WHEN marketplace = 'allegro' THEN external_id ELSE NULL END, "
            f"'CANCELLATION', 'MIGRATION', 'DONE', {login.format(col='buyer_login')}, "
            "order_date, :now, :now FROM orders "
            "WHERE UPPER(status) = 'CANCELLED' OR UPPER(COALESCE(fulfillment_status, '')) "
            "= 'CANCELLED'"
        ),
        {"now": now},
    )
    statuses = ", ".join(f"'{s}'" for s in _REFUNDED_RETURN_STATUSES)
    # Zwrot pieniędzy przy zamówieniu już anulowanym -> "oba zdarzenia".
    bind.execute(
        sa.text(
            "UPDATE customer_cases SET kind = 'BOTH' WHERE EXISTS ("
            "SELECT 1 FROM customer_returns r WHERE r.marketplace = customer_cases.marketplace "
            "AND r.order_external_id = customer_cases.order_external_id "
            f"AND UPPER(r.status) IN ({statuses}))"
        )
    )
    bind.execute(
        sa.text(
            "INSERT INTO customer_cases (marketplace, order_external_id, allegro_order_id, "
            "kind, source, handling_status, buyer_login, order_date, created_at, updated_at) "
            "SELECT r.marketplace, r.order_external_id, "
            "CASE WHEN r.marketplace = 'allegro' THEN r.order_external_id ELSE NULL END, "
            f"'REFUND', 'MIGRATION', 'DONE', {login.format(col='MIN(r.buyer_login)')}, "
            "MIN(o.order_date), :now, :now "
            "FROM customer_returns r LEFT JOIN orders o ON o.marketplace = r.marketplace "
            "AND o.external_id = r.order_external_id "
            f"WHERE UPPER(r.status) IN ({statuses}) AND NOT EXISTS ("
            "SELECT 1 FROM customer_cases c WHERE c.marketplace = r.marketplace "
            "AND c.order_external_id = r.order_external_id) "
            "GROUP BY r.marketplace, r.order_external_id"
        ),
        {"now": now},
    )


def downgrade() -> None:
    """Usuwa rejestr i historię powodów."""
    op.drop_index("ix_customer_case_reason_changes_case_id", "customer_case_reason_changes")
    op.drop_table("customer_case_reason_changes")
    for column in ("order_external_id", "kind", "source", "handling_status", "reason"):
        op.drop_index(f"ix_customer_cases_{column}", "customer_cases")
    op.drop_table("customer_cases")
