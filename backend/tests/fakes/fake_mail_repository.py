"""Fake implementacja MailRepository - działa w pamięci, bez bazy danych."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.domain.entities.mail_message import MailMessage
from app.domain.interfaces.mail_repository import MailRepository


class FakeMailRepository(MailRepository):
    """Implementacja MailRepository trzymająca dane w liście Pythona - do testów jednostkowych."""

    def __init__(self) -> None:
        self._messages: dict[str, MailMessage] = {}

    async def exists(self, message_id: str) -> bool:
        return message_id in self._messages

    async def save(self, message: MailMessage) -> None:
        self._messages[message.message_id] = message

    async def get_recent(
        self,
        source: str | None = None,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MailMessage]:
        items = sorted(self._messages.values(), key=lambda m: m.received_at, reverse=True)
        if source:
            items = [m for m in items if m.source == source]
        if unread_only:
            items = [m for m in items if not m.is_read]
        return items[offset : offset + limit]

    async def get_by_id(self, message_id: str) -> MailMessage | None:
        return self._messages.get(message_id)

    async def mark_read(self, message_id: str) -> None:
        existing = self._messages.get(message_id)
        if existing:
            self._messages[message_id] = replace(existing, is_read=True)

    async def get_latest_received_at(self) -> datetime | None:
        if not self._messages:
            return None
        return max(m.received_at for m in self._messages.values())
