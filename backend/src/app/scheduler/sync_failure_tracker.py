"""
Licznik nieudanych synchronizacji - decyduje, KIEDY wysłać powiadomienie
o niedostępnym kanale.

Reguła z sekcji 04 koncepcji push jest jednoznaczna: powiadomienie
"Allegro nie odpowiedziało" leci **dopiero po drugiej nieudanej próbie**,
nigdy przy pojedynczym timeoucie.

Powód jest praktyczny: synchronizacja chodzi co 60 sekund, a Allegro
regularnie gubi pojedyncze żądania. Alarmowanie przy każdym takim
zdarzeniu dałoby kilkanaście powiadomień dziennie o niczym i użytkownik
wyłączyłby je w ogóle - razem z tymi, które są ważne.

Stan żyje w pamięci procesu, tak samo jak w `OrderPushBatcher`: restart
usługi co najwyżej przesunie próg o jedną próbę, a zapisywanie tego do
bazy przy każdym cyklu byłoby zapisem co minutę bez powodu.
"""

from __future__ import annotations

#: Po ilu z rzędu nieudanych próbach wysyłamy powiadomienie (sekcja 04).
FAILURES_BEFORE_ALERT = 2


class SyncFailureTracker:
    """Śledzi serie nieudanych synchronizacji per kanał."""

    def __init__(self, threshold: int = FAILURES_BEFORE_ALERT) -> None:
        self._threshold = threshold
        self._consecutive_failures: dict[str, int] = {}
        self._alerted: set[str] = set()

    def record_failure(self, channel: str) -> bool:
        """
        Odnotowuje nieudaną próbę.

        Returns:
            True, gdy TERAZ należy wysłać powiadomienie - czyli przy
            osiągnięciu progu. Kolejne awarie w tej samej serii zwracają
            False, żeby nie powtarzać tego samego alertu co minutę.
        """
        count = self._consecutive_failures.get(channel, 0) + 1
        self._consecutive_failures[channel] = count

        if count >= self._threshold and channel not in self._alerted:
            self._alerted.add(channel)
            return True
        return False

    def record_success(self, channel: str) -> None:
        """
        Zeruje serię po udanej synchronizacji.

        Dzięki temu kolejna awaria za tydzień znowu przejdzie pełną
        ścieżkę "dwie próby, potem alert", a nie odpali natychmiast.
        """
        self._consecutive_failures.pop(channel, None)
        self._alerted.discard(channel)
