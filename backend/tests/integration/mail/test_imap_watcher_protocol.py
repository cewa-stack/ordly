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
import pytest
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


def _build_html_message(
    message_id: str = "<html1@allegromail.pl>",
    sender: str = "Allegro <powiadomienia@allegro.pl>",
) -> bytes:
    """
    Mail JEDNOCZĘŚCIOWY `text/html` - dokładnie taki, jaki Allegro wysyła
    przy powiadomieniach o dyskusji, i dokładnie ten kształt, który
    wychodził w aplikacji jako surowe źródło.
    """
    message = EmailMessage()
    message["Message-ID"] = message_id
    message["From"] = sender
    message["Subject"] = "Dyskusja - nowa wiadomość od naszego doradcy"
    message["Date"] = "Sat, 08 Aug 2026 09:30:00 +0000"
    message.set_content(
        '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">\n'
        '<html lang="pl"><head><style>body{font-family:Arial}</style></head>'
        "<body><p>Dzie&#324; dobry,</p>"
        "<p>masz now&#261; wiadomo&#347;&#263; od naszego doradcy.</p>"
        "</body></html>",
        subtype="html",
    )
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

    async def test_token_allegro_lapie_takze_allegro_lokalnie(self, server: FakeImapServer):
        """
        KLUCZOWE DLA KONFIGURACJI NA PI. IMAP dopasowuje FROM po
        podciągu, więc token "allegro" łapie i `allegromail.pl`,
        i `allegrolokalnie.pl` - ale wpisana w `.env` DOMENA "allegro.pl"
        nie łapie żadnego z nich. Przy złej wartości `MAIL_WATCH_SENDERS`
        powiadomienia z Allegro Lokalnie w ogóle nie trafiają do ORDLY.
        """
        server.add_message(
            _build_message(
                message_id="<al1@allegrolokalnie.pl>",
                sender="Allegro Lokalnie <powiadomienia@allegrolokalnie.pl>",
                subject="Nowe zamówienie",
            )
        )

        z_tokenem = await _watcher(server).fetch_new_from_senders(["allegro"], _SINCE)
        z_domena = await _watcher(server).fetch_new_from_senders(["allegro.pl"], _SINCE)

        assert [m.message_id for m in z_tokenem] == ["<al1@allegrolokalnie.pl>"]
        assert z_tokenem[0].source == "allegro_lokalnie"
        assert z_domena == []

    async def test_pusta_skrzynka_zwraca_pusta_liste(self, server: FakeImapServer):
        messages = await _watcher(server).fetch_new_from_senders(["allegro"], _SINCE)

        assert messages == []

    async def test_podglad_maila_html_nie_zawiera_znacznikow(self, server: FakeImapServer):
        """
        Regresja buga "surowy kod HTML w skrzynce": mail jednoczęściowy
        `text/html` nie ma części `text/plain`, więc podgląd budowany z
        surowego payloadu zaczynał się od `<!DOCTYPE HTML ...`.
        """
        server.add_message(_build_html_message())

        messages = await _watcher(server).fetch_new_from_senders(["allegro"], _SINCE)

        assert len(messages) == 1
        preview = messages[0].body_preview
        assert "<" not in preview
        assert "DOCTYPE" not in preview
        assert "Dzień dobry" in preview


class TestFetchBodiesByMessageId:
    """Dociąganie pełnej treści pojedynczego maila na żądanie użytkownika."""

    async def test_znajduje_maila_po_message_id_i_oddaje_obie_wersje(
        self, server: FakeImapServer
    ):
        server.add_message(_build_message(message_id="<inny@allegromail.pl>"))
        server.add_message(_build_html_message())

        bodies = await _watcher(server).fetch_bodies_by_message_id("<html1@allegromail.pl>")

        assert bodies is not None
        assert bodies.html is not None
        assert bodies.html.startswith("<!DOCTYPE HTML")
        assert bodies.text is None

    async def test_nie_oznacza_maila_jako_przeczytanego(self, server: FakeImapServer):
        """Otwarcie wiadomości w ORDLY nie może zmienić jej stanu w Gmailu."""
        server.add_message(_build_html_message())

        await _watcher(server).fetch_bodies_by_message_id("<html1@allegromail.pl>")

        fetches = [cmd for cmd in server.commands if " FETCH " in f" {cmd} "]
        assert fetches, "watcher w ogóle nie pobrał wiadomości"
        for command in fetches:
            assert "BODY.PEEK[]" in command
            assert "RFC822" not in command

    async def test_brak_maila_na_serwerze_zwraca_none(self, server: FakeImapServer):
        """Mail skasowany w Gmailu to brak treści, a nie błąd połączenia."""
        server.add_message(_build_message())

        bodies = await _watcher(server).fetch_bodies_by_message_id("<niema@allegromail.pl>")

        assert bodies is None

    async def test_message_id_z_cudzyslowem_jest_odrzucone(self, server: FakeImapServer):
        """
        Cudzysłów w wartości pozwoliłby doczepić do komendy IMAP własne
        argumenty - odpowiednik SQL injection dla protokołu pocztowego.
        """
        server.add_message(_build_message())

        with pytest.raises(ValueError):
            await _watcher(server).fetch_bodies_by_message_id('<a" OR FROM "bank')

        assert not any("HEADER" in command for command in server.commands)
