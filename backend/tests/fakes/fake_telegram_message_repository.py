"""Fake implementacja TelegramMessageRepository - rejestr wiadomości w pamięci."""

from __future__ import annotations

from app.domain.interfaces.telegram_message_repository import (
    TelegramMessageRepository,
    TrackedMessage,
)


class FakeTelegramMessageRepository(TelegramMessageRepository):
    """Przechowuje identyfikatory wiadomości bota w zwykłej liście."""

    def __init__(self) -> None:
        self.messages: list[TrackedMessage] = []

    async def record(self, chat_id: int, message_id: int) -> None:
        self.messages.append(TrackedMessage(chat_id=chat_id, message_id=message_id))

    async def get_all(self) -> list[TrackedMessage]:
        return list(self.messages)

    async def delete_all(self) -> int:
        removed = len(self.messages)
        self.messages.clear()
        return removed
