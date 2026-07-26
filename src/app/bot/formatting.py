"""
Wspólne elementy formatowania wiadomości bota ORDLY.

Trzymanie separatora i wspólnych fragmentów w jednym miejscu gwarantuje,
że wszystkie komendy wyglądają spójnie - zmiana stylu w jednym miejscu
odświeża wygląd całego bota.
"""

from __future__ import annotations

DIVIDER = "─" * 22


def header(emoji: str, title: str) -> str:
    """Buduje pogrubiony nagłówek sekcji wraz z separatorem pod spodem."""
    return f"{emoji} <b>{title}</b>\n{DIVIDER}"
