"""Testy integracyjne SqliteOrdlakRepository na prawdziwej bazie SQLite."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.ordlak_generation import OrdlakGeneration
from app.repositories.sqlite_ordlak_repository import SqliteOrdlakRepository


def _generation(
    title: str = "Kubek ceramiczny biały 350 ml porcelana matowa do kawy herbaty",
    created_at: datetime | None = None,
    note: str = "Biały kubek z hurtowni",
) -> OrdlakGeneration:
    return OrdlakGeneration(
        id=None,
        created_at=created_at or datetime(2026, 8, 9, 12, 0, 0),
        user_note=note,
        condition="new",
        purchase_cost=25.0,
        inbound_shipping_cost=8.0,
        buyer_shipping_cost=12.0,
        commission_percent=10.0,
        target_margin_percent=30.0,
        photo_count=2,
        generated_title=title,
        generated_description_html="<p>Opis produktu.</p>",
        ai_condition_notes="Bez rys.",
        suggested_price=57.0,
    )


class TestSqliteOrdlakRepository:
    async def test_zapisuje_i_nadaje_id(self, in_memory_session: AsyncSession):
        repository = SqliteOrdlakRepository(in_memory_session)

        saved = await repository.save(_generation())

        assert saved.id is not None
        assert saved.generated_title.startswith("Kubek ceramiczny")
        assert saved.suggested_price == 57.0

    async def test_odczytuje_po_id(self, in_memory_session: AsyncSession):
        repository = SqliteOrdlakRepository(in_memory_session)
        saved = await repository.save(_generation())
        assert saved.id is not None

        loaded = await repository.get_by_id(saved.id)

        assert loaded is not None
        assert loaded.user_note == "Biały kubek z hurtowni"
        assert loaded.photo_count == 2
        assert loaded.ai_condition_notes == "Bez rys."

    async def test_nieistniejace_id_zwraca_none(self, in_memory_session: AsyncSession):
        repository = SqliteOrdlakRepository(in_memory_session)

        assert await repository.get_by_id(999) is None

    async def test_historia_najnowsze_pierwsze(self, in_memory_session: AsyncSession):
        repository = SqliteOrdlakRepository(in_memory_session)
        baza = datetime(2026, 8, 9, 12, 0, 0)
        await repository.save(_generation(created_at=baza, note="starszy"))
        await repository.save(_generation(created_at=baza + timedelta(hours=1), note="nowszy"))

        historia = await repository.get_recent()

        assert [g.user_note for g in historia] == ["nowszy", "starszy"]

    async def test_historia_respektuje_limit_i_offset(self, in_memory_session: AsyncSession):
        repository = SqliteOrdlakRepository(in_memory_session)
        baza = datetime(2026, 8, 9, 12, 0, 0)
        for index in range(3):
            await repository.save(
                _generation(created_at=baza + timedelta(hours=index), note=f"nr{index}")
            )

        strona = await repository.get_recent(limit=1, offset=1)

        assert [g.user_note for g in strona] == ["nr1"]

    async def test_finalize_nadpisuje_tylko_pola_koncowe(
        self, in_memory_session: AsyncSession
    ):
        """Oryginał modelu zostaje - historia ma pokazywać, co user poprawił."""
        repository = SqliteOrdlakRepository(in_memory_session)
        saved = await repository.save(_generation())
        assert saved.id is not None

        updated = await repository.update_final_texts(
            saved.id, "Nowy tytuł oferty", "<p>Nowy opis</p>"
        )

        assert updated is not None
        assert updated.title == "Nowy tytuł oferty"
        assert updated.description_html == "<p>Nowy opis</p>"
        assert updated.generated_title == saved.generated_title
        assert updated.generated_description_html == "<p>Opis produktu.</p>"

    async def test_finalize_nieistniejacej_generacji_zwraca_none(
        self, in_memory_session: AsyncSession
    ):
        repository = SqliteOrdlakRepository(in_memory_session)

        assert await repository.update_final_texts(999, "tytuł", "<p>opis</p>") is None
