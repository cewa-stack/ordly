"""Serwis dostępu do historii zdarzeń dla komendy /logs."""

from __future__ import annotations

from app.repositories.sqlite_event_repository import EventRecord, SqliteEventRepository


class EventsService:
    """Udostępnia historię zdarzeń systemowych do wyświetlenia użytkownikowi."""

    def __init__(self, event_repository: SqliteEventRepository) -> None:
        self._event_repository = event_repository

    async def get_recent_events(self, limit: int) -> list[EventRecord]:
        """Zwraca ostatnie zdarzenia posortowane od najnowszego."""
        return await self._event_repository.get_recent(limit)
