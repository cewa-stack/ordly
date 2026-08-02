"""
Pomocnicze funkcje czasu - jedno źródło prawdy dla "teraz" w UTC.

Cała aplikacja przechowuje czas jako naiwne datetime w UTC (tak są
zdefiniowane kolumny w bazie). `datetime.utcnow()` jest oznaczone jako
deprecated od Pythona 3.12, więc ten moduł jest jedynym miejscem,
które wie, jak poprawnie uzyskać naiwny czas UTC.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Zwraca bieżący czas UTC jako naiwny datetime (bez tzinfo)."""
    return datetime.now(UTC).replace(tzinfo=None)
