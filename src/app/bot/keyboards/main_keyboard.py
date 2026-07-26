"""Klawiatury inline/reply używane przez bota ORDLY."""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def build_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Buduje główną klawiaturę menu wyświetlaną po komendzie /start.

    Returns:
        Klawiatura z najczęściej używanymi komendami jako przyciski.
    """
    buttons = [
        [KeyboardButton(text="/orders"), KeyboardButton(text="/stats")],
        [KeyboardButton(text="/sync"), KeyboardButton(text="/health")],
        [KeyboardButton(text="/help")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
