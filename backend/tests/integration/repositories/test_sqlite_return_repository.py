"""
Testy integracyjne SqliteReturnRepository na prawdziwej bazie SQLite
in-memory (nie fake) - weryfikują poprawność zapytań SQL i constraintów.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from app.domain.exceptions.domain_exceptions import DuplicateReturnError
from app.repositories.sqlite_return_repository import SqliteReturnRepository


class TestSqliteReturnRepository:
    """Testy zapisu i deduplikacji zwrotów na prawdziwej bazie SQLAlchemy."""

    @pytest.mark.asyncio
    async def test_zapisuje_zwrot_i_exists_zwraca_true(self, in_memory_session, sample_return):
        """Zwrot zapisany repozytorium powinien być widoczny przez exists()."""
        repository = SqliteReturnRepository(in_memory_session)

        await repository.save(sample_return)
        await in_memory_session.commit()

        assert await repository.exists("allegro", sample_return.external_id) is True

    @pytest.mark.asyncio
    async def test_exists_zwraca_false_dla_niezapisanego_zwrotu(self, in_memory_session):
        """exists() powinno zwrócić False, gdy zwrot nigdy nie był zapisany."""
        repository = SqliteReturnRepository(in_memory_session)

        assert await repository.exists("allegro", "NIEISTNIEJACY") is False

    @pytest.mark.asyncio
    async def test_unique_constraint_blokuje_duplikat(self, in_memory_session, sample_return):
        """Próba zapisania tego samego (marketplace, external_id) drugi raz powinna zawieść."""
        repository = SqliteReturnRepository(in_memory_session)
        await repository.save(sample_return)
        await in_memory_session.commit()

        with pytest.raises(DuplicateReturnError):
            await repository.save(sample_return)

    @pytest.mark.asyncio
    async def test_get_recent_zwraca_najnowszy_zwrot_pierwszy(
        self, in_memory_session, sample_return
    ):
        """get_recent() powinno sortować malejąco po dacie zwrotu."""
        repository = SqliteReturnRepository(in_memory_session)
        older = replace(
            sample_return,
            external_id="RETURN-OLD",
            created_at=datetime(2026, 6, 1, 8, 0, 0),
        )
        newer = replace(
            sample_return,
            external_id="RETURN-NEW",
            created_at=datetime(2026, 7, 15, 9, 0, 0),
        )
        await repository.save(older)
        await repository.save(newer)
        await in_memory_session.commit()

        records = await repository.get_recent()

        assert [r.external_id for r in records] == ["RETURN-NEW", "RETURN-OLD"]

    @pytest.mark.asyncio
    async def test_get_recent_respektuje_limit_i_offset(
        self, in_memory_session, sample_return
    ):
        """Paginacja limit/offset powinna zwracać właściwy wycinek listy."""
        repository = SqliteReturnRepository(in_memory_session)
        for i in range(3):
            await repository.save(
                replace(
                    sample_return,
                    external_id=f"RETURN-{i}",
                    created_at=datetime(2026, 7, i + 1, 8, 0, 0),
                )
            )
        await in_memory_session.commit()

        records = await repository.get_recent(limit=1, offset=1)

        assert [r.external_id for r in records] == ["RETURN-1"]

    @pytest.mark.asyncio
    async def test_get_recent_pusta_baza_zwraca_pusta_liste(self, in_memory_session):
        """Brak zwrotów w bazie nie powinien wywalać błędu, tylko pustą listę."""
        repository = SqliteReturnRepository(in_memory_session)

        assert await repository.get_recent() == []
