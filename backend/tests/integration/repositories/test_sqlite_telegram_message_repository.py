"""Testy integracyjne SqliteTelegramMessageRepository na bazie SQLite in-memory."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.sqlite_telegram_message_repository import (
    SqliteTelegramMessageRepository,
)

_CHAT_ID = 123456789


async def test_record_bez_flush_utrwala_sie_po_commit(
    in_memory_session: AsyncSession,
) -> None:
    """record() nie flushuje, ale commit sesji utrwala wiersze."""
    repository = SqliteTelegramMessageRepository(in_memory_session)

    await repository.record(_CHAT_ID, 10)
    await repository.record(_CHAT_ID, 11)
    await in_memory_session.commit()

    tracked = await repository.get_all()

    assert [(m.chat_id, m.message_id) for m in tracked] == [
        (_CHAT_ID, 10),
        (_CHAT_ID, 11),
    ]


async def test_delete_all_czysci_rejestr_i_zwraca_liczbe(
    in_memory_session: AsyncSession,
) -> None:
    """delete_all() usuwa wszystkie wpisy i zwraca liczbę usuniętych."""
    repository = SqliteTelegramMessageRepository(in_memory_session)
    await repository.record(_CHAT_ID, 10)
    await repository.record(_CHAT_ID, 11)
    await in_memory_session.commit()

    removed = await repository.delete_all()
    await in_memory_session.commit()

    assert removed == 2
    assert await repository.get_all() == []
