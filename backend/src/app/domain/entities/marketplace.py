"""Encja domenowa reprezentująca marketplace jako pojęcie biznesowe."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Marketplace:
    """
    Reprezentacja marketplace (Allegro, Amazon, eBay...) w warstwie
    domenowej - używana np. do wyświetlania nazwy w wiadomościach
    Telegram, niezależnie od tego, ile pluginów jest zarejestrowanych.
    """

    code: str
    display_name: str
