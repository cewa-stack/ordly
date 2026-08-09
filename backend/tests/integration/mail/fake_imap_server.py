"""
Minimalny serwer IMAP na prawdziwym gnieździe TCP - do testów watchera.

Po co to, skoro są już testy jednostkowe `_extract_message_bytes`? Bo te
testy podawały ręcznie zmyślony kształt odpowiedzi FETCH (listę `bytes`) i
właśnie dlatego przepuściły błąd produkcyjny: prawdziwe `aioimaplib`
oddaje treść literału jako `bytearray`, nie `bytes`. Dopóki test nie
przechodzi PRAWDZIWEGO protokołu (literały, ramki, CRLF), potrafi
potwierdzać wyłącznie nasze własne wyobrażenie o bibliotece.

Serwer obsługuje dokładnie tyle, ile robi `ImapWatcher`: CAPABILITY,
LOGIN, SELECT, SEARCH, FETCH, LOGOUT. Zapisuje też wszystkie odebrane
komendy (`commands`), żeby test mógł sprawdzić, CO poszło na serwer -
np. że pobieranie używa `BODY.PEEK[]` i nie oznacza maili jako
przeczytanych.
"""

from __future__ import annotations

import asyncio
import email
import email.utils
import re
from datetime import date

_CRLF = b"\r\n"

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}  # fmt: skip

_FROM_RE = re.compile(r'FROM "([^"]*)"', re.IGNORECASE)
_SINCE_RE = re.compile(r"SINCE (\S+)", re.IGNORECASE)
_IMAP_DATE_RE = re.compile(r"^(\d{1,2})-([A-Za-z]{3})-(\d{4})$")


def parse_imap_date(raw: str) -> date | None:
    """
    Parsuje `09-Aug-2026`. Zwraca None dla formatu, którego prawdziwy serwer
    by nie przyjął (np. `09-sie-2026` z polskiego locale) - test ma wtedy
    zobaczyć brak wyników, a nie zawieszone połączenie.
    """
    match = _IMAP_DATE_RE.match(raw)
    if match is None:
        return None
    month = _MONTHS.get(match.group(2).lower())
    if month is None:
        return None
    return date(int(match.group(3)), month, int(match.group(1)))


class FakeImapServer:
    """Serwer IMAP w pamięci, słuchający na losowym porcie localhosta."""

    def __init__(self) -> None:
        self.messages: list[bytes] = []
        self.commands: list[str] = []
        self.port = 0
        self._server: asyncio.AbstractServer | None = None

    def add_message(self, raw: bytes) -> None:
        """Dokłada surową wiadomość RFC822 do skrzynki serwera."""
        self.messages.append(raw)

    async def start(self) -> None:
        """Startuje serwer na wolnym porcie i zapamiętuje go w `self.port`."""
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        """Zamyka serwer i czeka na zwolnienie gniazda."""
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        writer.write(b"* OK [CAPABILITY IMAP4rev1] Fake IMAP gotowy" + _CRLF)
        await writer.drain()

        while True:
            raw_line = await reader.readline()
            if not raw_line:
                break
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            self.commands.append(line)

            tag, _, rest = line.partition(" ")
            name = rest.split(" ", 1)[0].upper()

            if name == "CAPABILITY":
                writer.write(b"* CAPABILITY IMAP4rev1" + _CRLF)
                self._ok(writer, tag, "CAPABILITY")
            elif name == "LOGIN":
                self._ok(writer, tag, "LOGIN")
            elif name == "SELECT":
                writer.write(f"* {len(self.messages)} EXISTS".encode() + _CRLF)
                writer.write(f"{tag} OK [READ-WRITE] SELECT completed.".encode() + _CRLF)
            elif name == "SEARCH":
                found = self._search(rest)
                ids = " ".join(str(number) for number in found)
                writer.write(f"* SEARCH {ids}".rstrip().encode() + _CRLF)
                self._ok(writer, tag, "SEARCH")
            elif name == "FETCH":
                self._fetch(writer, tag, rest)
            elif name == "LOGOUT":
                writer.write(b"* BYE" + _CRLF)
                self._ok(writer, tag, "LOGOUT")
                await writer.drain()
                break
            else:
                writer.write(f"{tag} BAD nieobslugiwana komenda".encode() + _CRLF)
            await writer.drain()

        writer.close()

    @staticmethod
    def _ok(writer: asyncio.StreamWriter, tag: str, command: str) -> None:
        writer.write(f"{tag} OK {command} completed.".encode() + _CRLF)

    def _search(self, command: str) -> list[int]:
        """
        Filtruje wiadomości jak prawdziwy serwer: FROM to dopasowanie
        PODCIĄGU nagłówka (nie równość adresu), SINCE porównuje daty.
        """
        from_match = _FROM_RE.search(command)
        needle = from_match.group(1).lower() if from_match else ""

        since_match = _SINCE_RE.search(command)
        since = parse_imap_date(since_match.group(1)) if since_match else None
        if since_match is not None and since is None:
            return []

        found: list[int] = []
        for number, raw in enumerate(self.messages, start=1):
            message = email.message_from_bytes(raw)
            sender = str(message.get("From", "")).lower()
            if needle and needle not in sender:
                continue
            if since is not None:
                received = email.utils.parsedate_to_datetime(str(message.get("Date")))
                if received.date() < since:
                    continue
            found.append(number)
        return found

    def _fetch(self, writer: asyncio.StreamWriter, tag: str, command: str) -> None:
        parts = command.split(" ")
        number = int(parts[1])
        raw = self.messages[number - 1]
        # Prawdziwe serwery odpowiadają etykietą `BODY[]` nawet na
        # `BODY.PEEK[]` - watcher nie może polegać na echu swojej komendy.
        writer.write(f"* {number} FETCH (BODY[] {{{len(raw)}}}".encode() + _CRLF)
        writer.write(raw)
        writer.write(b")" + _CRLF)
        self._ok(writer, tag, "FETCH")
