"""
Testy integracyjne repozytorium szablonów odpowiedzi na prawdziwym SQLite.

Ryzykowne jest tu to, czego fake by nie pokazał: nadawanie `position`
(nowy szablon ma trafić na KONIEC listy, a nie między te, do których
ręka przywykła) i to, że `id` jest znane od razu po dodaniu - aplikacja
dostaje je w odpowiedzi i od razu może szablon edytować.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.sqlite_reply_template_repository import SqliteReplyTemplateRepository


@pytest.fixture
def repository(in_memory_session: AsyncSession) -> SqliteReplyTemplateRepository:
    return SqliteReplyTemplateRepository(in_memory_session)


class TestKolejnosc:
    async def test_nowy_szablon_trafia_na_koniec(self, repository: SqliteReplyTemplateRepository):
        first = await repository.add("Dziękuję", "Dziękuję za zakup.")
        second = await repository.add("Wysłane", "Numer: {numer_przesylki}")

        assert first.id is not None and second.id is not None
        assert second.position > first.position
        assert [t.title for t in await repository.list_all()] == ["Dziękuję", "Wysłane"]

    async def test_edycja_nie_przestawia_kolejnosci(
        self, repository: SqliteReplyTemplateRepository
    ):
        first = await repository.add("A", "a")
        await repository.add("B", "b")

        updated = await repository.update(first.id, "A2", "a2")

        assert updated is not None and updated.body == "a2"
        assert [t.title for t in await repository.list_all()] == ["A2", "B"]


class TestBrakujacySzablon:
    async def test_edycja_nieistniejacego_zwraca_none(
        self, repository: SqliteReplyTemplateRepository
    ):
        assert await repository.update(999, "x", "y") is None

    async def test_usuwanie_mowi_czy_bylo_co_usunac(
        self, repository: SqliteReplyTemplateRepository
    ):
        template = await repository.add("A", "a")

        assert await repository.delete(template.id) is True
        assert await repository.delete(template.id) is False
        assert await repository.list_all() == []
