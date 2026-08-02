"""Testy integracyjne SqliteMailRepository na prawdziwej bazie SQLite in-memory."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from app.repositories.sqlite_mail_repository import SqliteMailRepository


class TestSqliteMailRepository:
    """Testy zapisu i odczytu maili na prawdziwej bazie SQLAlchemy."""

    @pytest.mark.asyncio
    async def test_zapisuje_mail_i_exists_zwraca_true(
        self, in_memory_session, sample_mail_message
    ):
        repository = SqliteMailRepository(in_memory_session)

        await repository.save(sample_mail_message)
        await in_memory_session.commit()

        assert await repository.exists(sample_mail_message.message_id) is True

    @pytest.mark.asyncio
    async def test_exists_false_dla_niezapisanego_maila(self, in_memory_session):
        repository = SqliteMailRepository(in_memory_session)

        assert await repository.exists("<brak@example.com>") is False

    @pytest.mark.asyncio
    async def test_get_recent_sortuje_od_najnowszego(
        self, in_memory_session, sample_mail_message
    ):
        repository = SqliteMailRepository(in_memory_session)
        older = replace(
            sample_mail_message,
            message_id="<older@allegromail.pl>",
            received_at=datetime(2026, 6, 1),
        )
        newer = replace(
            sample_mail_message,
            message_id="<newer@allegromail.pl>",
            received_at=datetime(2026, 7, 15),
        )
        await repository.save(older)
        await repository.save(newer)
        await in_memory_session.commit()

        messages = await repository.get_recent()

        assert [m.message_id for m in messages] == [
            "<newer@allegromail.pl>",
            "<older@allegromail.pl>",
        ]

    @pytest.mark.asyncio
    async def test_get_recent_filtruje_po_source(self, in_memory_session, sample_mail_message):
        repository = SqliteMailRepository(in_memory_session)
        allegro_mail = replace(sample_mail_message, message_id="<a@x.pl>", source="allegro")
        olx_mail = replace(sample_mail_message, message_id="<o@x.pl>", source="olx")
        await repository.save(allegro_mail)
        await repository.save(olx_mail)
        await in_memory_session.commit()

        messages = await repository.get_recent(source="olx")

        assert [m.message_id for m in messages] == ["<o@x.pl>"]

    @pytest.mark.asyncio
    async def test_get_recent_filtruje_nieprzeczytane(
        self, in_memory_session, sample_mail_message
    ):
        repository = SqliteMailRepository(in_memory_session)
        unread = replace(sample_mail_message, message_id="<unread@x.pl>", is_read=False)
        read = replace(sample_mail_message, message_id="<read@x.pl>", is_read=True)
        await repository.save(unread)
        await repository.save(read)
        await in_memory_session.commit()

        messages = await repository.get_recent(unread_only=True)

        assert [m.message_id for m in messages] == ["<unread@x.pl>"]

    @pytest.mark.asyncio
    async def test_mark_read_oznacza_mail(self, in_memory_session, sample_mail_message):
        repository = SqliteMailRepository(in_memory_session)
        await repository.save(sample_mail_message)
        await in_memory_session.commit()

        await repository.mark_read(sample_mail_message.message_id)
        await in_memory_session.commit()

        updated = await repository.get_by_id(sample_mail_message.message_id)
        assert updated is not None
        assert updated.is_read is True

    @pytest.mark.asyncio
    async def test_get_latest_received_at_zwraca_najnowsza_date(
        self, in_memory_session, sample_mail_message
    ):
        repository = SqliteMailRepository(in_memory_session)
        older = replace(
            sample_mail_message, message_id="<older@x.pl>", received_at=datetime(2026, 6, 1)
        )
        newer = replace(
            sample_mail_message, message_id="<newer@x.pl>", received_at=datetime(2026, 7, 15)
        )
        await repository.save(older)
        await repository.save(newer)
        await in_memory_session.commit()

        assert await repository.get_latest_received_at() == datetime(2026, 7, 15)

    @pytest.mark.asyncio
    async def test_get_latest_received_at_puste_zwraca_none(self, in_memory_session):
        repository = SqliteMailRepository(in_memory_session)

        assert await repository.get_latest_received_at() is None
