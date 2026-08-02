"""
Middleware wstrzykujące kontener oraz sesję bazy danych do każdego handlera.

Otwiera jedną sesję SQLAlchemy per przychodząca aktualizacja Telegram
i zamyka ją (z commit/rollback) po zakończeniu obsługi.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.bot.middlewares.session_context import (
    reset_current_session,
    set_current_session,
)

if TYPE_CHECKING:
    from app.container import Container


class ContainerMiddleware(BaseMiddleware):
    """Wstrzykuje kontener DI oraz świeżą sesję bazy danych do handlera."""

    def __init__(self, container: Container) -> None:
        self._container = container

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """
        Otwiera sesję na czas obsługi jednej aktualizacji Telegram.

        Sesja jest też udostępniana przez ContextVar, aby middleware sesji
        bota mógł zapisać ID odpowiedzi w tej samej transakcji (bez rywalizacji
        o blokadę zapisu SQLite z sesją handlera).
        """
        data["container"] = self._container
        async with self._container.session_scope() as session:
            data["session"] = session
            token = set_current_session(session)
            try:
                return await handler(event, data)
            finally:
                reset_current_session(token)
