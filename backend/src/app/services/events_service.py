"""Serwis dostępu do historii zdarzeń dla komendy /logs."""

from __future__ import annotations

from app.repositories.sqlite_event_repository import EventRecord, SqliteEventRepository

#: Wpisy zapisywane przy KAŻDEJ synchronizacji (co 60 s). Przydatne przy
#: diagnozie w Telegramie, ale na liście "co się dziś działo" zagłuszają
#: zamówienia, zwroty i ostrzeżenia.
SYNC_EVENT_TYPES = ("SyncStarted", "SyncFinished")


class EventsService:
    """Udostępnia historię zdarzeń systemowych do wyświetlenia użytkownikowi."""

    def __init__(self, event_repository: SqliteEventRepository) -> None:
        self._event_repository = event_repository

    async def get_recent_events(
        self, limit: int, include_sync: bool = True
    ) -> list[EventRecord]:
        """Zwraca ostatnie zdarzenia posortowane od najnowszego."""
        return await self._event_repository.get_recent(
            limit, exclude_types=() if include_sync else SYNC_EVENT_TYPES
        )
