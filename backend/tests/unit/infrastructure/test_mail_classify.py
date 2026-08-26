"""Testy jednostkowe klasyfikacji nadawcy maila."""

from __future__ import annotations

from app.infrastructure.mail.classify import classify_sender


class TestClassifySender:
    def test_rozpoznaje_allegro(self):
        assert classify_sender("noreply@allegromail.pl") == "allegro"
        assert classify_sender("Allegro <powiadomienia@allegro.pl>") == "allegro"

    def test_rozpoznaje_allegro_lokalnie_jako_osobny_kanal(self):
        """
        Allegro Lokalnie to inny serwis niż Allegro.pl: bez API, bez
        możliwości zarządzania zamówieniem z ORDLY. Wspólna etykieta
        sugerowałaby użytkownikowi zakres, którego tam nie ma.
        """
        assert classify_sender("powiadomienia@allegrolokalnie.pl") == "allegro_lokalnie"
        assert (
            classify_sender("Allegro Lokalnie <noreply@allegrolokalnie.pl>")
            == "allegro_lokalnie"
        )

    def test_allegro_lokalnie_nie_wpada_do_allegro(self):
        """
        Regresja kolejności warunków: "allegrolokalnie.pl" ZAWIERA
        podciąg "allegro", więc sprawdzanie Allegro.pl jako pierwszego
        zagarniało wszystkie powiadomienia z Lokalnie pod złą etykietę.
        """
        assert classify_sender("powiadomienia@allegrolokalnie.pl") != "allegro"

    def test_rozpoznaje_olx(self):
        assert classify_sender("noreply@olx.pl") == "olx"

    def test_nieznany_nadawca_to_other(self):
        assert classify_sender("ktos@example.com") == "other"
