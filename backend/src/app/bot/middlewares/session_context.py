"""
Kontekst bieżącej sesji handlera Telegram (ContextVar).

Umożliwia middleware sesji bota zapisanie identyfikatora wysłanej
wiadomości w TEJ SAMEJ sesji, w której działa handler komendy. Jest to
kluczowe dla poprawności: handler piszący do bazy (np. /stock set) trzyma
blokadę zapisu SQLite do czasu commitu. Gdyby śledzenie wiadomości
otwierało osobne połączenie, jego zapis czekałby na tę blokadę, zawieszając
odpowiedź na komendę. Zapis w tej samej sesji używa tego samego połączenia
i nie powoduje rywalizacji o blokadę.

ContextVar jest kopiowany per-task asyncio, więc każda równolegle
obsługiwana aktualizacja Telegram ma własną, izolowaną wartość.
"""

from __future__ import annotations

from contextvars import ContextVar, Token

from sqlalchemy.ext.asyncio import AsyncSession

_current_session: ContextVar[AsyncSession | None] = ContextVar(
    "current_handler_session", default=None
)


def set_current_session(session: AsyncSession) -> Token[AsyncSession | None]:
    """Ustawia sesję bieżącego handlera i zwraca token do jej zresetowania."""
    return _current_session.set(session)


def reset_current_session(token: Token[AsyncSession | None]) -> None:
    """Przywraca poprzednią wartość ContextVar (po zakończeniu handlera)."""
    _current_session.reset(token)


def get_current_session() -> AsyncSession | None:
    """Zwraca sesję bieżącego handlera lub None, gdy wysyłka jest poza handlerem."""
    return _current_session.get()
