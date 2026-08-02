"""Testy jednostkowe parsowania wiadomości RFC822 (IMAP watcher)."""

from __future__ import annotations

from email.message import EmailMessage

from app.infrastructure.mail.imap_watcher import _extract_message_bytes, _parse_message


def _build_raw_message(
    message_id: str = "<test123@allegromail.pl>",
    sender: str = "Allegro <noreply@allegromail.pl>",
    subject: str = "Masz nowe zamówienie",
    body: str = "Dzień dobry, otrzymałeś nowe zamówienie. Sprawdź szczegóły w panelu sprzedawcy.",
) -> bytes:
    msg = EmailMessage()
    msg["Message-ID"] = message_id
    msg["From"] = sender
    msg["Subject"] = subject
    msg["Date"] = "Wed, 01 Jul 2026 10:00:00 +0000"
    msg.set_content(body)
    return msg.as_bytes()


class TestParseMessage:
    def test_mapuje_pelna_wiadomosc(self):
        raw = _build_raw_message()

        message = _parse_message(raw)

        assert message is not None
        assert message.message_id == "<test123@allegromail.pl>"
        assert "noreply@allegromail.pl" in message.sender
        assert message.subject == "Masz nowe zamówienie"
        assert message.source == "allegro"
        assert "nowe zamówienie" in message.body_preview
        assert message.received_at.year == 2026
        assert message.received_at.month == 7
        assert message.received_at.day == 1

    def test_brak_message_id_zwraca_none(self):
        msg = EmailMessage()
        msg["From"] = "ktos@example.com"
        msg["Subject"] = "Bez Message-ID"
        msg.set_content("tresc")

        assert _parse_message(msg.as_bytes()) is None

    def test_klasyfikuje_olx(self):
        raw = _build_raw_message(
            message_id="<xyz@olx.pl>", sender="OLX <noreply@olx.pl>", subject="Wiadomość"
        )

        message = _parse_message(raw)

        assert message is not None
        assert message.source == "olx"

    def test_nieznany_nadawca_klasyfikowany_jako_other(self):
        raw = _build_raw_message(sender="ktos@example.com")

        message = _parse_message(raw)

        assert message is not None
        assert message.source == "other"

    def test_obcina_podglad_tresci_do_500_znakow(self):
        raw = _build_raw_message(body="x" * 1000)

        message = _parse_message(raw)

        assert message is not None
        assert len(message.body_preview) == 500


class TestExtractMessageBytes:
    def test_wybiera_najdluzsza_linie_jako_tresc(self):
        lines = [
            b"1 FETCH (RFC822 {123}",
            b"x" * 500,
            b")",
        ]

        result = _extract_message_bytes(lines)

        assert result == b"x" * 500

    def test_brak_kandydatow_zwraca_none(self):
        assert _extract_message_bytes([b"short", b")"]) is None
