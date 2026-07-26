"""
Tworzenie instancji bota i dispatchera aiogram.

Ten moduł jest jedynym miejscem tworzenia obiektu Bot - reszta
aplikacji otrzymuje gotowe instancje przez Dependency Injection.
Bot występuje pod nazwą "ORDLY".
"""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.core.config import TelegramSettings


def create_bot(settings: TelegramSettings) -> Bot:
    """
    Tworzy instancję bota Telegram (ORDLY) skonfigurowaną z domyślnym
    HTML parse mode.

    Args:
        settings: Konfiguracja Telegram (token, admin chat id).

    Returns:
        Skonfigurowana instancja Bot.
    """
    return Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    """
    Tworzy dispatcher aiogram, do którego rejestrowane będą routery handlerów.

    Returns:
        Nowa instancja Dispatcher (bez zarejestrowanych jeszcze routerów).
    """
    return Dispatcher()
