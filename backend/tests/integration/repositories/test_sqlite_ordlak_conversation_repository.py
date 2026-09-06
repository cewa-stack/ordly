"""
Testy integracyjne repozytorium rozmów z asystentem na prawdziwym SQLite.

Fake w pamięci nie złapałby tego, co tu jest ryzykowne: sortowania po
`updated_at`, licznika wiadomości liczonego JOIN-em i kasowania wiadomości
przy usuwaniu wątku (SQLite egzekwuje ON DELETE CASCADE tylko przy
włączonym PRAGMA foreign_keys, więc repozytorium robi to jawnie).
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.ordlak_conversation_model import OrdlakMessageModel
from app.repositories.sqlite_ordlak_conversation_repository import (
    SqliteOrdlakConversationRepository,
)


@pytest.fixture
def repository(in_memory_session: AsyncSession) -> SqliteOrdlakConversationRepository:
    return SqliteOrdlakConversationRepository(in_memory_session)


async def _count_messages(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(OrdlakMessageModel))).scalar_one()


class TestZapisIOdczyt:
    async def test_wiadomosci_wracaja_od_najstarszej(
        self, repository: SqliteOrdlakConversationRepository
    ):
        conversation = await repository.create("Ile sprzedałem?")
        assert conversation.id is not None
        await repository.append(conversation.id, "user", "Ile sprzedałem?")
        await repository.append(
            conversation.id, "assistant", "Trzy zamówienia.", ("podsumowanie_sprzedazy",)
        )

        loaded = await repository.get(conversation.id)

        assert loaded is not None
        assert [m.role for m in loaded.messages] == ["user", "assistant"]
        assert loaded.messages[1].used_tools == ("podsumowanie_sprzedazy",)
        assert loaded.message_count == 2

    async def test_brak_narzedzi_to_pusta_krotka_a_nie_pusty_napis(
        self, repository: SqliteOrdlakConversationRepository
    ):
        """`"".split(",")` daje `['']` - stąd jawny filtr w repozytorium."""
        conversation = await repository.create("Cześć")
        assert conversation.id is not None
        await repository.append(conversation.id, "assistant", "Cześć!")

        loaded = await repository.get(conversation.id)

        assert loaded is not None
        assert loaded.messages[0].used_tools == ()

    async def test_nieistniejacy_watek_to_none(
        self, repository: SqliteOrdlakConversationRepository
    ):
        assert await repository.get(404) is None


class TestListaRozmow:
    async def test_ostatnio_uzywana_jest_na_gorze(
        self, repository: SqliteOrdlakConversationRepository
    ):
        first = await repository.create("Pierwsza")
        second = await repository.create("Druga")
        assert first.id is not None and second.id is not None
        await repository.append(first.id, "user", "dopisek")

        recent = await repository.list_recent()

        assert [c.id for c in recent] == [first.id, second.id]

    async def test_liczy_wiadomosci_kazdego_watku(
        self, repository: SqliteOrdlakConversationRepository
    ):
        pusta = await repository.create("Pusta")
        pelna = await repository.create("Pełna")
        assert pusta.id is not None and pelna.id is not None
        await repository.append(pelna.id, "user", "raz")
        await repository.append(pelna.id, "assistant", "dwa")

        counts = {c.id: c.message_count for c in await repository.list_recent()}

        assert counts[pusta.id] == 0
        assert counts[pelna.id] == 2

    async def test_lista_nie_wozi_tresci_wiadomosci(
        self, repository: SqliteOrdlakConversationRepository
    ):
        conversation = await repository.create("Rozmowa")
        assert conversation.id is not None
        await repository.append(conversation.id, "user", "długie pytanie")

        recent = await repository.list_recent()

        assert recent[0].messages == ()

    async def test_limit_ucina_liste(self, repository: SqliteOrdlakConversationRepository):
        for index in range(5):
            await repository.create(f"Rozmowa {index}")

        assert len(await repository.list_recent(limit=2)) == 2


class TestUsuwanie:
    async def test_usuwa_watek_razem_z_wiadomosciami(
        self,
        repository: SqliteOrdlakConversationRepository,
        in_memory_session: AsyncSession,
    ):
        conversation = await repository.create("Do skasowania")
        assert conversation.id is not None
        await repository.append(conversation.id, "user", "pytanie")
        await repository.append(conversation.id, "assistant", "odpowiedź")

        assert await repository.delete(conversation.id) is True

        assert await repository.get(conversation.id) is None
        assert await _count_messages(in_memory_session) == 0

    async def test_nie_rusza_cudzych_wiadomosci(
        self,
        repository: SqliteOrdlakConversationRepository,
        in_memory_session: AsyncSession,
    ):
        zostaje = await repository.create("Zostaje")
        znika = await repository.create("Znika")
        assert zostaje.id is not None and znika.id is not None
        await repository.append(zostaje.id, "user", "moje")
        await repository.append(znika.id, "user", "cudze")

        await repository.delete(znika.id)

        assert await _count_messages(in_memory_session) == 1
        loaded = await repository.get(zostaje.id)
        assert loaded is not None
        assert loaded.messages[0].content == "moje"

    async def test_usuniecie_nieistniejacego_zwraca_false(
        self, repository: SqliteOrdlakConversationRepository
    ):
        assert await repository.delete(404) is False
