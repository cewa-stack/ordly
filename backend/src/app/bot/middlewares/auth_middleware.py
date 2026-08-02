"""
Middleware autoryzacji - odrzuca wszystkie wiadomości spoza
skonfigurowanego chat_id administratora.

ORDLY jest osobistym asystentem jednej osoby, nie publicznym botem -
middleware chroni przed sytuacją, w której ktoś inny (np. znający
wyciekły token) próbowałby wydawać komendy.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from loguru import logger


class AdminOnlyMiddleware(BaseMiddleware):
    """Przepuszcza wyłącznie aktualizacje pochodzące od administratora."""

    def __init__(self, admin_chat_id: int) -> None:
        """
        Args:
            admin_chat_id: Jedyny chat_id, z którego akceptowane są komendy.
        """
        self._admin_chat_id = admin_chat_id

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """
        Weryfikuje chat_id przed przekazaniem zdarzenia do handlera.

        Polityka default-deny: aktualizacje, z których nie da się
        jednoznacznie odczytać chat_id administratora (nieznany typ,
        brak nadawcy), są odrzucane - a nie przepuszczane.
        """
        chat_id = self._extract_chat_id(event)

        if chat_id != self._admin_chat_id:
            logger.warning("Odrzucono nieautoryzowaną próbę dostępu z chat_id={}", chat_id)
            return None

        return await handler(event, data)

    @staticmethod
    def _extract_chat_id(event: TelegramObject) -> int | None:
        """Wyciąga chat_id z różnych typów aktualizacji Telegram."""
        if isinstance(event, Update):
            if event.message:
                return event.message.chat.id
            if event.edited_message:
                return event.edited_message.chat.id
            if event.callback_query and event.callback_query.message:
                return event.callback_query.message.chat.id
        return None
