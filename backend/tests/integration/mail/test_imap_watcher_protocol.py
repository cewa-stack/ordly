"""
Testy watchera IMAP na prawdziwym protokole (patrz `fake_imap_server`).

Każdy test w tym pliku przechodzi pełną ścieżkę: gniazdo TCP, greeting,
CAPABILITY, LOGIN, SELECT, SEARCH, FETCH z literałem i LOGOUT.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from email.message import EmailMessage

import aioimaplib
import pytest_asyncio

from app.infrastructure.mail.imap_watcher import ImapWatcher
from tests.integration.mail.fake_imap_server import FakeImapServer

_SINCE = datetime(2026, 8, 1, 0, 0, 0)


def _build_message(
    message_id: str = "<a1@allegromail.pl>",
    sender: str = "Allegro <noreply@allegromail.pl>",
    subject: str = "Masz nowe zamówienie",
    body: str = "Kupujący opłacił zamówienie. Szczegóły w panelu sprzedawcy.",
    date_header: str = "Sat, 08 Aug 2026 09:30:00 +0000",
) -> bytes:
    message = EmailMessage()
    message["Message-ID"] = message_id
    message["From"] = sender
    message["Subject"] = subject
    message["Date"] = date_header
    message.set_content(body)
    return message.as_bytes()


@pytest_asyncio.fixture
async def server() -> AsyncIterator[FakeImapServer]:
    fake = FakeImapServer()
    await fake.start()
    try:
        yield fake
    finally:
        await fake.stop()


def _watcher(server: FakeImapServer) -> ImapWatcher:
    return ImapWatcher(
        host="127.0.0.1",
        port=server.port,
        user="sklep@gmail.com",
        password="haslo-aplikacji",
        client_factory=lambda: aioimaplib.IMAP4(host="127.0.0.1", port=server.port),
    )


class TestFetchNewFromSenders:
    async def test_pobiera_i_parsuje_maila_przez_prawdziwy_protokol(
        self, server: FakeImapServer
    ):
        """
        Test regresji błędu "skrzynka zawsze pusta".

        `aioimaplib` oddaje treść literału jako `bytearray`, a filtr
        `isinstance(line, bytes)` w `_extract_message_bytes` wycinał
        dokładnie tę linię - SEARCH znajdował maile, FETCH je pobierał, a
        watcher po cichu wyrzucał wszystkie i zwracał pustą listę.
        """
        server.add_message(_build_message())

        messages = await _watcher(server).fetch_new_from_senders(["allegro"], _SINCE)

        assert len(messages) == 1
        assert messages[0].message_id == "<a1@allegromail.pl>"
        assert messages[0].subject == "Masz nowe zamówienie"
        assert messages[0].source == "allegro"
        assert "Kupujący opłacił zamówienie" in messages[0].body_preview

    async def test_nie_oznacza_maili_jako_przeczytanych(self, server: FakeImapServer):
        """
        `RFC822` i `BODY[]` ustawiają na serwerze flagę \\Seen - czyli
        oznaczałyby użytkownikowi maile jako przeczytane w Gmailu przy
        każdej synchronizacji. Moduł jest tylko-do-odczytu, więc musi
        używać wariantu PEEK.
        """
        server.add_message(_build_message())

        await _watcher(server).fetch_new_from_senders(["allegro"], _SINCE)

        fetches = [cmd for cmd in server.commands if " FETCH " in f" {cmd} "]
        assert fetches, "watcher w ogóle nie pobrał wiadomości"
        for command in fetches:
            assert "BODY.PEEK[]" in command
            assert "RFC822" not in command

    async def test_deduplikuje_maila_znalezionego_przez_dwa_wzorce(
        self, server: FakeImapServer
    ):
        """Ten sam mail pasujący do dwóch wzorców nadawcy ma wrócić raz."""
        server.add_message(_build_message())

        messages = await _watcher(server).fetch_new_from_senders(
            ["allegro", "allegromail"], _SINCE
        )

        assert len(messages) == 1

    async def test_pomija_maile_od_innych_nadawcow(self, server: FakeImapServer):
        server.add_message(_build_message())
        server.add_message(
            _build_message(message_id="<b2@example.com>", sender="Bank <kontakt@example.com>")
        )

        messages = await _watcher(server).fetch_new_from_senders(["allegro"], _SINCE)

        assert [m.message_id for m in messages] == ["<a1@allegromail.pl>"]

    async def test_pomija_maile_starsze_niz_since(self, server: FakeImapServer):
        server.add_message(
            _build_message(
                message_id="<stary@allegromail.pl>",
                date_header="Mon, 01 Jun 2026 09:00:00 +0000",
            )
        )
        server.add_message(_build_message())

        messages = await _watcher(server).fetch_new_from_senders(["allegro"], _SINCE)

        assert [m.message_id for m in messages] == ["<a1@allegromail.pl>"]

    async def test_data_since_jest_niezalezna_od_locale(self, server: FakeImapServer):
        """
        `strftime("%b")` daje "sie" zamiast "Aug" przy polskim LC_TIME, co
        serwer odrzuca. Data w komendzie musi być zawsze angielska.
        """
        server.add_message(_build_message())

        await _watcher(server).fetch_new_from_senders(["allegro"], _SINCE)

        searches = [cmd for cmd in server.commands if " SEARCH " in cmd]
        assert searches
        assert all("SINCE 01-Aug-2026" in cmd for cmd in searches)

    async def test_wzorzec_allegro_pl_nie_lapie_domeny_allegromail_pl(
        self, server: FakeImapServer
    ):
        """
        Dokumentuje powód zmiany domyślnego `MAIL_WATCH_SENDERS`. IMAP
        dopasowuje FROM po podciągu, a w `noreply@allegromail.pl` nie ma
        podciągu "allegro.pl" - po "allegro" idzie tam "mail.pl". Wpisanie
        domeny zamiast tokenu cicho gubi wszystkie powiadomienia Allegro.
        """
        server.add_message(_build_message())

        z_domena = await _watcher(server).fetch_new_from_senders(["allegro.pl"], _SINCE)
        z_tokenem = await _watcher(server).fetch_new_from_senders(["allegro"], _SINCE)

        assert z_domena == []
        assert len(z_tokenem) == 1

    async def test_pusta_skrzynka_zwraca_pusta_liste(self, server: FakeImapServer):
        messages = await _watcher(server).fetch_new_from_senders(["allegro"], _SINCE)

        assert messages == []
