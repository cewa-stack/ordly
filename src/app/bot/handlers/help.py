"""Handler komendy /help."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.formatting import header

router = Router(name="help")

_HELP_TEXT = (
    f"{header('📖', 'ORDLY - DOSTĘPNE KOMENDY')}\n\n"
    "🛒 <b>Zamówienia</b>\n"
    "/orders — lista ostatnich zamówień\n"
    "/order [numer] — szczegóły zamówienia\n"
    "/search [tekst] — wyszukaj zamówienie lub produkt\n\n"
    "🚚 <b>Przesyłki</b>\n"
    "/tracking [numer] — status przesyłki (pobierany na żądanie)\n\n"
    "📦 <b>Magazyn</b>\n"
    "/stock — stan magazynu\n"
    "/stock set|add|remove [SKU] [ilość] — korekta stanu\n"
    "/stock report — raport magazynowy z prognozą\n"
    "/stock buy — lista zakupów\n"
    "/stock history [SKU] — historia zmian\n\n"
    "📊 <b>Status i statystyki</b>\n"
    "/stats — statystyki sprzedaży\n"
    "/health — status działania asystenta\n"
    "/sync — wymuś natychmiastową synchronizację\n"
    "/logs — ostatnie zdarzenia systemowe\n\n"
    "❓ /help — ta wiadomość"
)


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    """Wyświetla listę dostępnych komend."""
    await message.answer(_HELP_TEXT)
