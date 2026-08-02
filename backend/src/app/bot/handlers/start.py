"""Handler komendy /start."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.bot.formatting import header
from app.bot.keyboards.main_keyboard import build_main_menu_keyboard

router = Router(name="start")


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    """Wysyła wiadomość powitalną wraz z głównym menu."""
    text = (
        f"{header('🤖', 'ORDLY')}\n\n"
        "Personal Commerce Intelligence Platform.\n"
        "Monitoruję Twoje zamówienia 24/7 i powiadomię Cię "
        "natychmiast o każdym nowym zamówieniu.\n\n"
        "Pełną listę komend znajdziesz pod /help 👇"
    )
    await message.answer(text, reply_markup=build_main_menu_keyboard())
