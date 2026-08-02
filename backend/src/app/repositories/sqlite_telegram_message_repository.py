"""Implementacja TelegramMessageRepository oparta o SQLAlchemy + SQLite."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.telegram_message_model import TelegramMessageModel
from app.domain.interfaces.telegram_message_repository import (
    TelegramMessageRepository,
    TrackedMessage,
)


class SqliteTelegramMessageRepository(TelegramMessageRepository):
    """Rejestr identyfikatorów wiadomości bota przechowywany w SQLite."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Args:
            session: Aktywna sesja SQLAlchemy, wstrzykiwana per operacja
                przez Dependency Injection.
        """
        self._session = session

    async def record(self, chat_id: int, message_id: int) -> None:
        """
        Dodaje identyfikator wysłanej wiadomości do sesji (bez flush).

        Celowo NIE wywołujemy flush - dzięki temu (przy autoflush=False)
        zapis nie zajmuje blokady zapisu SQLite w trakcie działania handlera
        ani subskrybentów zdarzeń. Wiersz jest utrwalany dopiero przy commit
        sesji (przez ContainerMiddleware lub session_scope), co eliminuje
        rywalizację o blokadę z równoległymi sesjami.
        """
        self._session.add(TelegramMessageModel(chat_id=chat_id, message_id=message_id))

    async def get_all(self) -> list[TrackedMessage]:
        """Zwraca wszystkie zarejestrowane wiadomości, od najstarszej."""
        stmt = select(TelegramMessageModel).order_by(TelegramMessageModel.id)
        result = await self._session.execute(stmt)
        return [
            TrackedMessage(chat_id=m.chat_id, message_id=m.message_id)
            for m in result.scalars().all()
        ]

    async def delete_all(self) -> int:
        """Usuwa wszystkie wpisy rejestru. Zwraca liczbę usuniętych wierszy."""
        count_stmt = select(func.count()).select_from(TelegramMessageModel)
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar_one() or 0

        await self._session.execute(delete(TelegramMessageModel))
        await self._session.flush()
        return total
