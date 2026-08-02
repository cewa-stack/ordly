"""Repozytorium zdarzeń (audit log) oparte o SQLite."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.event_model import EventModel


@dataclass(frozen=True, slots=True)
class EventRecord:
    """Reprezentacja zdarzenia odczytanego z bazy do wyświetlenia w /logs."""

    event_type: str
    level: str
    created_at: datetime


class SqliteEventRepository:
    """Zapisuje i odczytuje historię zdarzeń systemowych z SQLite."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self, event_type: str, level: str = "INFO", payload: dict | None = None
    ) -> None:
        """Zapisuje nowe zdarzenie w tabeli events."""
        model = EventModel(
            event_type=event_type,
            level=level,
            payload_json=json.dumps(payload, default=str) if payload else None,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_recent(self, limit: int) -> list[EventRecord]:
        """Zwraca ostatnie zdarzenia posortowane od najnowszego."""
        stmt = select(EventModel).order_by(EventModel.created_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return [
            EventRecord(event_type=m.event_type, level=m.level, created_at=m.created_at)
            for m in result.scalars().all()
        ]
