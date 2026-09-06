"""Implementacja OrdlakConversationRepository oparta o SQLAlchemy + SQLite."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.ordlak_conversation_model import (
    OrdlakConversationModel,
    OrdlakMessageModel,
)
from app.domain.entities.ordlak_conversation import (
    ChatRole,
    OrdlakConversation,
    OrdlakMessage,
)
from app.domain.interfaces.ordlak_conversation_repository import (
    OrdlakConversationRepository,
)
from app.utils.time import utc_now


def _split_tools(raw: str) -> tuple[str, ...]:
    """Zamienia zapis "a,b,c" na krotkę. Pusty string to brak narzędzi, nie `('',)`."""
    return tuple(name for name in raw.split(",") if name)


def _to_message(model: OrdlakMessageModel) -> OrdlakMessage:
    return OrdlakMessage(
        id=model.id,
        role=cast(ChatRole, model.role),
        content=model.content,
        created_at=model.sent_at,
        used_tools=_split_tools(model.used_tools),
    )


class SqliteOrdlakConversationRepository(OrdlakConversationRepository):
    """Wątki rozmowy przechowywane w SQLite przez SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, title: str) -> OrdlakConversation:
        now = utc_now()
        model = OrdlakConversationModel(title=title, created_at=now, updated_at=now)
        self._session.add(model)
        await self._session.flush()
        return OrdlakConversation(
            id=model.id, title=model.title, created_at=now, updated_at=now
        )

    async def get(self, conversation_id: int) -> OrdlakConversation | None:
        model = await self._session.get(OrdlakConversationModel, conversation_id)
        if model is None:
            return None

        stmt = (
            select(OrdlakMessageModel)
            .where(OrdlakMessageModel.conversation_id == conversation_id)
            .order_by(OrdlakMessageModel.sent_at, OrdlakMessageModel.id)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        messages = tuple(_to_message(row) for row in rows)
        return OrdlakConversation(
            id=model.id,
            title=model.title,
            created_at=model.created_at,
            updated_at=model.updated_at,
            message_count=len(messages),
            messages=messages,
        )

    async def list_recent(self, limit: int = 30) -> list[OrdlakConversation]:
        # Licznik wiadomości jednym LEFT JOIN-em zamiast zapytania na wątek -
        # lista rozmów pokazuje go przy każdym wierszu, a wątków bywa
        # kilkadziesiąt.
        counts = (
            select(
                OrdlakMessageModel.conversation_id.label("conversation_id"),
                func.count().label("total"),
            )
            .group_by(OrdlakMessageModel.conversation_id)
            .subquery()
        )
        stmt = (
            select(OrdlakConversationModel, func.coalesce(counts.c.total, 0))
            .outerjoin(counts, counts.c.conversation_id == OrdlakConversationModel.id)
            .order_by(OrdlakConversationModel.updated_at.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            OrdlakConversation(
                id=model.id,
                title=model.title,
                created_at=model.created_at,
                updated_at=model.updated_at,
                message_count=int(total),
            )
            for model, total in rows
        ]

    async def append(
        self,
        conversation_id: int,
        role: ChatRole,
        content: str,
        used_tools: tuple[str, ...] = (),
    ) -> OrdlakMessage:
        now = utc_now()
        model = OrdlakMessageModel(
            conversation_id=conversation_id,
            role=role,
            content=content,
            used_tools=",".join(used_tools),
            sent_at=now,
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)

        conversation = await self._session.get(OrdlakConversationModel, conversation_id)
        if conversation is not None:
            conversation.updated_at = now

        await self._session.flush()
        return _to_message(model)

    async def delete(self, conversation_id: int) -> bool:
        # Wiadomości kasujemy jawnie: SQLite egzekwuje ON DELETE CASCADE
        # tylko przy włączonym PRAGMA foreign_keys, a poleganie na
        # ustawieniu połączenia zostawiłoby tu ciche sieroty.
        await self._session.execute(
            delete(OrdlakMessageModel).where(
                OrdlakMessageModel.conversation_id == conversation_id
            )
        )
        # `rowcount` istnieje na kursorze DBAPI, ale nie w typie `Result` -
        # stąd `CursorResult`, który go deklaruje.
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                delete(OrdlakConversationModel).where(
                    OrdlakConversationModel.id == conversation_id
                )
            ),
        )
        await self._session.flush()
        return bool(result.rowcount)
