"""
Pomocnicze funkcje czasu - jedno źródło prawdy dla "teraz" w UTC.

Cała aplikacja przechowuje czas jako naiwne datetime w UTC (tak są
zdefiniowane kolumny w bazie). `datetime.utcnow()` jest oznaczone jako
deprecated od Pythona 3.12, więc ten moduł jest jedynym miejscem,
które wie, jak poprawnie uzyskać naiwny czas UTC.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

LOCAL_TIMEZONE = ZoneInfo("Europe/Warsaw")


def utc_now() -> datetime:
    """Zwraca bieżący czas UTC jako naiwny datetime (bez tzinfo)."""
    return datetime.now(UTC).replace(tzinfo=None)


def local_now() -> datetime:
    """
    Zwraca bieżący czas w strefie użytkownika (Europe/Warsaw).

    Potrzebne wszędzie tam, gdzie decyzja zależy od tego, która jest
    godzina DLA CZŁOWIEKA, a nie w UTC - np. godziny ciszy powiadomień
    22:00-7:00. Latem różnica wynosi 2 godziny, więc liczenie tego na
    UTC wyciszałoby powiadomienia od 20:00.

    Zwraca datetime świadomy strefy - w odróżnieniu od `utc_now()`,
    który celowo jest naiwny, bo trafia do bazy.
    """
    return datetime.now(LOCAL_TIMEZONE)


def local_today() -> date:
    """Dzisiejsza data w Polsce - "dziś" tak, jak rozumie je użytkownik."""
    return local_now().date()


def local_midnight_utc(day: date) -> datetime:
    """
    Północ podanego dnia w Polsce jako naiwny UTC - granica doby do
    zapytań po bazie.

    Liczenie "dziś" od północy UTC przesuwało dobę o godzinę zimą i o
    dwie latem: o 1:00 w nocy ekran Start pokazywał jeszcze wczorajszą
    sprzedaż, a zamówienie z 0:30 lądowało we wczorajszym słupku.
    Strefa jest liczona dla KONKRETNEGO dnia, więc zmiana czasu
    w marcu i październiku nie przesuwa granicy.
    """
    midnight = datetime(day.year, day.month, day.day, tzinfo=LOCAL_TIMEZONE)
    return midnight.astimezone(UTC).replace(tzinfo=None)


def to_local(value: datetime) -> datetime:
    """Zamienia naiwny czas UTC z bazy na czas w Polsce (świadomy strefy)."""
    return value.replace(tzinfo=UTC).astimezone(LOCAL_TIMEZONE)
