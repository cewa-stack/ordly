"""Fake implementacja OrdlakConversationRepository - rozmowy w pamięci."""

from __future__ import annotations

from dataclasses import replace

from app.domain.entities.ordlak_conversation import (
    ChatRole,
    OrdlakConversation,
    OrdlakMessage,
)
from app.domain.interfaces.ordlak_conversation_repository import (
    OrdlakConversationRepository,
)
from app.utils.time import utc_now


class FakeOrdlakConversationRepository(OrdlakConversationRepository):
    """Trzyma wątki w słowniku, z zachowaniem kolejności wiadomości."""

    def __init__(self) -> None:
        self.conversations: dict[int, OrdlakConversation] = {}
        self._next_id = 1

    async def create(self, title: str) -> OrdlakConversation:
        now = utc_now()
        conversation = OrdlakConversation(
            id=self._next_id, title=title, created_at=now, updated_at=now
        )
        self.conversations[self._next_id] = conversation
        self._next_id += 1
        return conversation

    async def get(self, conversation_id: int) -> OrdlakConversation | None:
        return self.conversations.get(conversation_id)

    async def list_recent(self, limit: int = 30) -> list[OrdlakConversation]:
        ordered = sorted(
            self.conversations.values(), key=lambda c: c.updated_at, reverse=True
        )
        # Lista rozmów nie wozi treści - tak samo jak implementacja SQLite.
        return [replace(conversation, messages=()) for conversation in ordered[:limit]]

    async def append(
        self,
        conversation_id: int,
        role: ChatRole,
        content: str,
        used_tools: tuple[str, ...] = (),
    ) -> OrdlakMessage:
        conversation = self.conversations[conversation_id]
        message = OrdlakMessage(
            id=len(conversation.messages) + 1,
            role=role,
            content=content,
            created_at=utc_now(),
            used_tools=used_tools,
        )
        self.conversations[conversation_id] = replace(
            conversation,
            messages=(*conversation.messages, message),
            message_count=conversation.message_count + 1,
            updated_at=message.created_at,
        )
        return message

    async def delete(self, conversation_id: int) -> bool:
        return self.conversations.pop(conversation_id, None) is not None
