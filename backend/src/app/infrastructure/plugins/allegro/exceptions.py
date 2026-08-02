"""Wyjątki specyficzne dla integracji z Allegro."""

from __future__ import annotations

from app.domain.exceptions.domain_exceptions import DomainError


class AllegroApiError(DomainError):
    """Allegro API zwróciło błąd (kod HTTP != 2xx, poza przypadkami obsłużonymi osobno)."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Allegro API error {status_code}: {detail}")


class AllegroAuthorizationPendingError(DomainError):
    """Trwa oczekiwanie na zatwierdzenie autoryzacji przez użytkownika w przeglądarce."""
