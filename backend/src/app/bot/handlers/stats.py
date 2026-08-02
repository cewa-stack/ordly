"""Handler komendy /stats."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import header
from app.container import Container

router = Router(name="stats")


@router.message(Command("stats"))
async def handle_stats(message: Message, container: Container, session: AsyncSession) -> None:
    """Wyświetla podsumowanie statystyk sprzedaży."""
    stats_service = container.stats_service(session)

    try:
        stats = await stats_service.get_summary()
    except Exception:
        logger.exception("Błąd podczas generowania statystyk")
        await message.answer("Wystąpił błąd podczas generowania statystyk.")
        return

    await message.answer(
        f"{header('📊', 'STATYSTYKI SPRZEDAŻY')}\n\n"
        "📅 <b>Dzisiaj</b>\n"
        f"   Zamówienia: {stats.orders_today}\n"
        f"   Przychód: {stats.revenue_today:.2f} PLN\n\n"
        "🗓 <b>Ten miesiąc</b>\n"
        f"   Zamówienia: {stats.orders_this_month}\n"
        f"   Przychód: {stats.revenue_this_month:.2f} PLN\n\n"
        f"📦 Łącznie zamówień w bazie: {stats.total_orders}"
    )
