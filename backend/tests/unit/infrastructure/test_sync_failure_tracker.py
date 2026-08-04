"""
Testy progu alertu o niedostępnym kanale: powiadomienie dopiero po
DRUGIEJ nieudanej próbie z rzędu (sekcja 04 koncepcji push).

Synchronizacja chodzi co 60 sekund i Allegro regularnie gubi pojedyncze
żądania - bez tego progu użytkownik dostawałby kilkanaście powiadomień
dziennie o niczym.
"""

from __future__ import annotations

from app.scheduler.sync_failure_tracker import SyncFailureTracker


class TestSyncFailureTracker:
    """Zachowanie licznika serii awarii."""

    def test_pojedynczy_timeout_nie_alarmuje(self):
        tracker = SyncFailureTracker()

        assert tracker.record_failure("allegro") is False

    def test_druga_awaria_z_rzedu_alarmuje(self):
        tracker = SyncFailureTracker()

        tracker.record_failure("allegro")

        assert tracker.record_failure("allegro") is True

    def test_kolejne_awarie_nie_powtarzaja_alertu(self):
        """Inaczej ten sam alert leciałby co minutę do skutku."""
        tracker = SyncFailureTracker()
        tracker.record_failure("allegro")
        tracker.record_failure("allegro")

        assert tracker.record_failure("allegro") is False
        assert tracker.record_failure("allegro") is False

    def test_udana_synchronizacja_zeruje_serie(self):
        """
        Po powrocie kanału do żywych kolejna awaria ma znowu przejść
        pełną ścieżkę "dwie próby, potem alert".
        """
        tracker = SyncFailureTracker()
        tracker.record_failure("allegro")
        tracker.record_failure("allegro")

        tracker.record_success("allegro")

        assert tracker.record_failure("allegro") is False
        assert tracker.record_failure("allegro") is True

    def test_kanaly_sa_liczone_osobno(self):
        """Awaria Allegro nie może uzbrajać alertu dla Amazona."""
        tracker = SyncFailureTracker()

        tracker.record_failure("allegro")

        assert tracker.record_failure("amazon") is False
