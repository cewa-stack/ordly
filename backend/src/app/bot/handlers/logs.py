"""Handler komendy /logs - ostatnie zdarzenia systemowe."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import header
from app.container import Container

router = Router(name="logs")

_LEVEL_ICONS = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "🔴"}


@router.message(Command("logs"))
async def handle_logs(message: Message, container: Container, session: AsyncSession) -> None:
    """Wyświetla ostatnie 15 zdarzeń zapisanych w tabeli events."""
    events_service = container.events_service(session)

    try:
        events = await events_service.get_recent_events(limit=15)
    except Exception:
        logger.exception("Błąd podczas pobierania logów")
        await message.answer("Wystąpił błąd podczas pobierania logów.")
        return

    title = header("📜", "OSTATNIE ZDARZENIA")

    if not events:
        await message.answer(f"{title}\n\nBrak zarejestrowanych zdarzeń.")
        return

    lines = [title, ""]
    for event in events:
        icon = _LEVEL_ICONS.get(event.level, "•")
        timestamp = event.created_at.strftime("%Y-%m-%d %H:%M")
        lines.append(f"{icon} <code>{timestamp}</code>  {event.event_type}")

    await message.answer("\n".join(lines))
