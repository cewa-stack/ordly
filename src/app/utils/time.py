"""
Pomocnicze funkcje czasu - jedno źródło prawdy dla "teraz" w UTC.

Cała aplikacja przechowuje czas jako naiwne datetime w UTC (tak są
zdefiniowane kolumny w bazie). `datetime.utcnow()` jest oznaczone jako
deprecated od Pythona 3.12, więc ten moduł jest jedynym miejscem,
które wie, jak poprawnie uzyskać naiwny czas UTC.
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

WARSAW_TZ = ZoneInfo("Europe/Warsaw")


def utc_now() -> datetime:
    """Zwraca bieżący czas UTC jako naiwny datetime (bez tzinfo)."""
    return datetime.now(UTC).replace(tzinfo=None)


def warsaw_day_start_utc(now: datetime | None = None) -> datetime:
    """
    Zwraca początek bieżącego dnia (00:00 czasu Warszawy) jako naiwny UTC.

    Zamówienia są przechowywane w bazie jako naiwny czas UTC, a przypomnienie
    o niewysłanych zamówieniach działa według doby lokalnej (Europe/Warsaw).
    Ta funkcja przelicza "dzisiaj od północy" w Warszawie na granicę w UTC,
    gotową do porównania z kolumną order_date.

    Args:
        now: Bieżący czas jako naiwny UTC (domyślnie utc_now()) - parametr
            ułatwia testowanie bez zależności od zegara systemowego.
    """
    now_utc = now if now is not None else utc_now()
    now_warsaw = now_utc.replace(tzinfo=UTC).astimezone(WARSAW_TZ)
    day_start_warsaw = now_warsaw.replace(hour=0, minute=0, second=0, microsecond=0)
    return day_start_warsaw.astimezone(UTC).replace(tzinfo=None)
