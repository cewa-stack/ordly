"""
Próg zbiorczy powiadomień o zamówieniach (sekcja 04 koncepcji push):
**3 zamówienia w 15 minut**.

Problem, który to rozwiązuje: synchronizacja potrafi wciągnąć naraz
kilkanaście zamówień z nocy. Bez progu telefon dostaje kilkanaście
osobnych wibracji pod rząd i użytkownik wyłącza powiadomienia w ogóle -
czyli tracimy też te pojedyncze, które naprawdę są pilne.

Jak to działa:

- Pierwsze i drugie zamówienie w oknie idą osobno, z pełnymi danymi.
- Trzecie **przełącza okno w tryb zbiorczy**: zamiast trzeciego
  osobnego powiadomienia leci jedno "3 nowe zamówienia" obejmujące
  wszystkie z okna.
- Każde kolejne w tym samym oknie AKTUALIZUJE to zbiorcze
  ("4 nowe zamówienia", "5 nowych zamówień") - `many_new_orders` nie
  ustawia własnego `collapse_key`, więc kolejne powiadomienie zastępuje
  poprzednie zamiast dokładać się do stosu.

Klasa jest świadomie bezstanowa wobec bazy - okno żyje w pamięci
procesu. Restart usługi zeruje licznik i najwyżej przepuści jedno
powiadomienie za dużo; przechowywanie tego w SQLite byłoby zapisem
przy każdym zamówieniu po to, żeby uniknąć jednej wibracji.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.entities.order import Order
from app.utils.time import utc_now

BATCH_THRESHOLD = 3
BATCH_WINDOW = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class BatchDecision:
    """
    Co zrobić z właśnie przyjętym zamówieniem.

    Dokładnie jedno z pól jest ustawione - albo wysyłamy pojedyncze
    powiadomienie, albo zbiorcze obejmujące całe okno.
    """

    single: Order | None = None
    collective: tuple[Order, ...] = ()


class OrderPushBatcher:
    """Decyduje, czy zamówienie idzie osobno, czy wchodzi do zbiorczego."""

    def __init__(self) -> None:
        self._window: list[tuple[datetime, Order]] = []

    def accept(self, order: Order, *, now: datetime | None = None) -> BatchDecision:
        """
        Przyjmuje nowe zamówienie i zwraca decyzję o sposobie wysyłki.

        Args:
            order: Zamówienie, o którym mamy powiadomić.
            now: Czas do testów - domyślnie bieżący UTC.

        Returns:
            `BatchDecision` z wypełnionym `single` albo `collective`.
        """
        moment = now or utc_now()
        self._forget_older_than(moment - BATCH_WINDOW)
        self._window.append((moment, order))

        if len(self._window) < BATCH_THRESHOLD:
            return BatchDecision(single=order)

        return BatchDecision(collective=tuple(item for _, item in self._window))

    def _forget_older_than(self, cutoff: datetime) -> None:
        """Usuwa z okna zamówienia starsze niż 15 minut."""
        self._window = [entry for entry in self._window if entry[0] > cutoff]
