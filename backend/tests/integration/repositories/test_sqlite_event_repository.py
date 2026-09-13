"""
Dziennik zdarzeń - odsiewanie wpisów synchronizacji.

Zgłoszony objaw: lista "Dziś w systemie" w desktopie była zapchana
naprzemiennymi "Start/Koniec synchronizacji" (dwa wpisy co minutę),
więc zamówienia i zwroty w ogóle się na niej nie mieściły.
"""

from __future__ import annotations

from app.repositories.sqlite_event_repository import SqliteEventRepository
from app.services.events_service import SYNC_EVENT_TYPES, EventsService


async def _seed(repository: SqliteEventRepository) -> None:
    for event_type in ("SyncStarted", "OrderCreated", "SyncFinished", "SyncStarted"):
        await repository.record(event_type=event_type)


class TestOdsiewanieSynchronizacji:
    async def test_pomija_wpisy_synchronizacji_w_zapytaniu(self, in_memory_session):
        repository = SqliteEventRepository(in_memory_session)
        await _seed(repository)

        events = await repository.get_recent(10, exclude_types=SYNC_EVENT_TYPES)

        assert [event.event_type for event in events] == ["OrderCreated"]

    async def test_limit_liczy_sie_po_odsianiu(self, in_memory_session):
        """
        Odsianie w SQL, nie po pobraniu: przy limicie 1 ma wrócić zamówienie,
        a nie pusta lista po wyrzuceniu jednego wpisu synchronizacji.
        """
        repository = SqliteEventRepository(in_memory_session)
        await _seed(repository)

        events = await EventsService(repository).get_recent_events(1, include_sync=False)

        assert [event.event_type for event in events] == ["OrderCreated"]

    async def test_domyslnie_zwraca_wszystko(self, in_memory_session):
        """Telegram /logs i starsze wywołania dalej widzą pełny dziennik."""
        repository = SqliteEventRepository(in_memory_session)
        await _seed(repository)

        events = await EventsService(repository).get_recent_events(10)

        assert len(events) == 4
