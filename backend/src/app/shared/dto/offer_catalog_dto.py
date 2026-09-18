"""DTO synchronizacji katalogu ofert marketplace."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CatalogUpsertResult:
    """Co zmieniło się w katalogu przy dosuwaniu go do listy z API."""

    added: int
    removed: int


@dataclass(frozen=True, slots=True)
class CatalogSyncResult:
    """
    Podsumowanie synchronizacji katalogu z marketplace.

    `added` i `removed` są tu po to, żeby przycisk synchronizacji miał co
    powiedzieć. Sam `fetched` nie odróżnia "pobrałem 40 ofert, wszystkie
    już znane" od "pobrałem 40, w tym 3 nowe" - a po to właśnie klika się
    synchronizację po wystawieniu czegoś nowego.
    """

    marketplace: str
    fetched: int
    added: int
    removed: int
    synced_at: datetime
