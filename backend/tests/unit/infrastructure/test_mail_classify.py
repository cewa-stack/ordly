"""Testy jednostkowe klasyfikacji nadawcy maila."""

from __future__ import annotations

from app.infrastructure.mail.classify import classify_sender


class TestClassifySender:
    def test_rozpoznaje_allegro(self):
        assert classify_sender("noreply@allegromail.pl") == "allegro"
        assert classify_sender("Allegro <powiadomienia@allegro.pl>") == "allegro"

    def test_rozpoznaje_olx(self):
        assert classify_sender("noreply@olx.pl") == "olx"

    def test_nieznany_nadawca_to_other(self):
        assert classify_sender("ktos@example.com") == "other"
