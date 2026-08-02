"""Handler komendy /health."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import header
from app.container import Container

router = Router(name="health")


@router.message(Command("health"))
async def handle_health(message: Message, container: Container, session: AsyncSession) -> None:
    """Wyświetla status działania asystenta (uptime, ostatnia synchronizacja, baza)."""
    health_service = container.health_service(session)
    status = await health_service.check()

    all_ok = status.database_ok and status.marketplace_connection_ok
    title_emoji = "💚" if all_ok else "🔴"
    db_icon = "✅" if status.database_ok else "❌"
    marketplace_icon = "✅" if status.marketplace_connection_ok else "❌"

    await message.answer(
        f"{header(title_emoji, 'STATUS ORDLY')}\n\n"
        f"⏱ Uptime: {status.uptime_human}\n"
        f"🔄 Ostatnia synchronizacja: {status.last_sync_human}\n\n"
        f"{db_icon} Baza danych\n"
        f"{marketplace_icon} Połączenie z Allegro"
    )
