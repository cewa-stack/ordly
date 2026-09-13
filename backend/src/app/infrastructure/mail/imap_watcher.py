"""
Watcher IMAP - wykrywa nowe maile od skonfigurowanych nadawcow (Allegro/OLX).

Tylko-do-odczytu: wylacznie SEARCH + FETCH, nigdy nie usuwa ani nie
modyfikuje niczego na serwerze pocztowym.
"""

from __future__ import annotations

import contextlib
import email
import email.utils
from collections.abc import Callable
from datetime import UTC, datetime
from email.header import decode_header
from email.message import Message

import aioimaplib

from app.domain.entities.mail_message import MailMessage
from app.infrastructure.mail.classify import classify_sender
from app.infrastructure.mail.mime import (
    MailBodies,
    extract_bodies,
    html_to_plain_text,
    looks_like_markup,
)
from app.utils.time import utc_now

_BODY_PREVIEW_LENGTH = 500

# Skróty miesięcy wymagane przez IMAP SEARCH (RFC 3501). Świadomie NIE
# uzywamy `strftime("%b")` - to formatowanie zalezy od LC_TIME procesu, wiec
# na maszynie z polska lokalizacja dawaloby "sie" zamiast "Aug" i serwer
# odrzucalby kazde zapytanie SEARCH.
_IMAP_MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)  # fmt: skip


class ImapConnectionError(Exception):
    """Połączenie, logowanie albo wyszukiwanie IMAP nie powiodło się."""


class ImapLoginRejectedError(ImapConnectionError):
    """
    Serwer odpowiedział na LOGIN odmową - połączenie było, ale login lub
    hasło nie przeszły (albo serwer odrzucił je z innego powodu, który
    podał w odpowiedzi). W odróżnieniu od zerwanego łącza samo ponawianie
    tu nie pomoże, więc alert mówi, że trzeba zajrzeć do Ustawień.

    Limit jednoczesnych połączeń to też odmowa LOGIN, ale mija sama -
    dostaje zwykły `ImapConnectionError` (patrz `_login_rejected_error`).
    """


ClientFactory = Callable[[], aioimaplib.IMAP4]

# Wszystko, czym aioimaplib potrafi przerwać rozmowę z serwerem: zerwane
# gniazdo (OSError), przekroczony czas komendy (TimeoutError z
# `asyncio.wait_for`, CommandTimeout przy FETCH) i błędy protokołu (Abort).
# Bez tej listy timeout w środku SEARCH leciał do FastAPI jako surowe 500
# i aplikacja nie wiedziała nawet, że chodzi o pocztę.
_IMAP_FAILURES = (OSError, TimeoutError, aioimaplib.AioImapException)

_SERVER_REASON_MAX_LENGTH = 200


class ImapWatcher:
    """Odczytuje maile od skonfigurowanych nadawców przez IMAP (tylko odczyt)."""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        client_factory: ClientFactory | None = None,
    ) -> None:
        """
        Args:
            host: Serwer IMAP.
            port: Port IMAP (zwykle 993).
            user: Login skrzynki.
            password: Hasło aplikacji (nie zwykłe hasło konta).
            client_factory: Fabryka klienta IMAP - domyślnie `IMAP4_SSL`.
                Podmienialna w testach na zwykłe `IMAP4` wskazujące lokalny
                serwer testowy, żeby dało się przejść PRAWDZIWY protokół
                (SEARCH + FETCH z literałami) bez ręcznego udawania kształtu
                odpowiedzi - to właśnie takie udawanie przepuściło błąd
                `bytearray` opisany przy `_extract_message_bytes`.
        """
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._client_factory = client_factory or (
            lambda: aioimaplib.IMAP4_SSL(host=host, port=port)
        )

    async def fetch_new_from_senders(
        self, senders: list[str], since: datetime
    ) -> list[MailMessage]:
        """
        Zwraca maile od podanych nadawców, nadesłane od `since`.

        Jedno zapytanie SEARCH per nadawca - IMAP SEARCH nie wspiera
        czytelnie OR na wszystkich serwerach, więc bezpieczniej iterować.
        """
        client = await self._open_inbox()

        since_str = _format_imap_date(since)
        messages: list[MailMessage] = []
        seen_ids: set[str] = set()
        try:
            for sender in senders:
                search_response = await client.search(f'FROM "{sender}" SINCE {since_str}')
                if search_response.result != "OK" or not search_response.lines:
                    continue
                raw_ids = search_response.lines[0].split()
                for raw_id in raw_ids:
                    raw_bytes = await _fetch_raw_message(client, raw_id)
                    if raw_bytes is None:
                        continue
                    message = _parse_message(raw_bytes)
                    if message is None or message.message_id in seen_ids:
                        continue
                    seen_ids.add(message.message_id)
                    messages.append(message)
        except _IMAP_FAILURES as exc:
            raise ImapConnectionError(
                f"Serwer IMAP {self._host} przerwał pobieranie poczty ({_describe(exc)})"
            ) from exc
        finally:
            await _close_quietly(client)
        return messages

    async def fetch_bodies_by_message_id(self, message_id: str) -> MailBodies | None:
        """
        Pobiera pełną treść JEDNEGO maila, wskazanego nagłówkiem Message-ID.

        Wywoływane dopiero wtedy, gdy użytkownik otworzy wiadomość - pełne
        treści maili świadomie NIE lądują w SQLite (patrz `MailboxService`).
        Powód jest praktyczny: mail reklamowy z obrazkami w `data:` potrafi
        ważyć kilka MB, a baza na Pi jest codziennie kopiowana przez
        `VACUUM INTO`, więc każdy zapisany megabajt mnoży się przez liczbę
        kopii zapasowych.

        Returns:
            Treść maila albo `None`, gdy nie ma go już na serwerze
            (np. użytkownik skasował go w Gmailu) - to nie jest błąd
            połączenia, tylko brak wiadomości.

        Raises:
            ImapConnectionError: Gdy połączenie/logowanie IMAP zawiedzie.
            ValueError: Gdy `message_id` zawiera znaki, których nie da się
                bezpiecznie wstawić do komendy IMAP.
        """
        criteria = f'HEADER Message-ID "{_quote_for_imap(message_id)}"'
        client = await self._open_inbox()
        try:
            search_response = await client.search(criteria)
            if search_response.result != "OK" or not search_response.lines:
                return None
            raw_ids = search_response.lines[0].split()
            if not raw_ids:
                return None
            # Gdyby ten sam Message-ID leżał w skrzynce dwa razy (przekazany
            # mail, ręczna kopia), bierzemy najnowszy numer - starsze i tak
            # mają tę samą treść.
            raw_bytes = await _fetch_raw_message(client, raw_ids[-1])
            if raw_bytes is None:
                return None
            return extract_bodies(email.message_from_bytes(raw_bytes))
        except _IMAP_FAILURES as exc:
            raise ImapConnectionError(
                f"Serwer IMAP {self._host} przerwał pobieranie treści maila ({_describe(exc)})"
            ) from exc
        finally:
            await _close_quietly(client)

    async def _open_inbox(self) -> aioimaplib.IMAP4:
        """
        Łączy się, loguje i wybiera INBOX - wspólny start każdej operacji.

        Każda porażka po nawiązaniu połączenia ZAMYKA je przed rzuceniem
        błędu. Wcześniej odrzucone logowanie zostawiało otwarte gniazdo,
        a Gmail pozwala na 15 jednoczesnych połączeń na konto - seria
        nieudanych synchronizacji mogła więc sama wyczerpać ten limit
        i blokować logowanie nawet po poprawieniu hasła.
        """
        client: aioimaplib.IMAP4 | None = None
        try:
            client = self._client_factory()
            await client.wait_hello_from_server()
        except _IMAP_FAILURES as exc:
            # Nieosiągalny host/port albo zerwane TLS - bez tego opakowania
            # surowy OSError leciał do FastAPI jako 500 "Internal Server
            # Error" i użytkownik nie wiedział, że chodzi o pocztę.
            if client is not None:
                await _close_quietly(client)
            raise ImapConnectionError(
                f"Brak połączenia z serwerem IMAP {self._host}:{self._port} ({_describe(exc)})"
            ) from exc

        try:
            login_response = await client.login(self._user, self._password)
            if login_response.result != "OK":
                raise _login_rejected_error(login_response.lines, self._password)

            select_response = await client.select("INBOX")
            if select_response.result != "OK":
                raise ImapConnectionError("Nie udało się otworzyć skrzynki INBOX")
        except ImapConnectionError:
            await _close_quietly(client)
            raise
        except _IMAP_FAILURES as exc:
            await _close_quietly(client)
            raise ImapConnectionError(
                f"Serwer IMAP {self._host} nie odpowiedział przy logowaniu ({_describe(exc)})"
            ) from exc
        return client


def _describe(exc: BaseException) -> str:
    """
    Krótki opis wyjątku do komunikatu dla użytkownika.

    `str(TimeoutError())` to pusty napis - bez tej zamiany komunikat
    kończyłby się pustym nawiasem „()" i nie mówił, co się stało.
    """
    if isinstance(exc, TimeoutError | aioimaplib.CommandTimeout):
        return "przekroczony czas oczekiwania"
    return str(exc) or type(exc).__name__


def _decode_server_lines(lines: list[bytes | bytearray | str], secret: str) -> str:
    """
    Składa tekst odpowiedzi serwera w jedną linię do pokazania w aplikacji.

    Hasło jest wycinane na wszelki wypadek - żaden znany serwer go nie
    odsyła, ale ten komunikat trafia do toastu i logów, więc nie może
    zależeć od uprzejmości serwera.
    """
    parts: list[str] = []
    for line in lines:
        text = line.decode("utf-8", errors="replace") if isinstance(line, bytes | bytearray) else line
        text = " ".join(text.split())
        if text:
            parts.append(text)
    reason = " ".join(parts)
    if secret:
        reason = reason.replace(secret, "***")
    if len(reason) > _SERVER_REASON_MAX_LENGTH:
        reason = reason[: _SERVER_REASON_MAX_LENGTH - 1] + "…"
    return reason


def _login_rejected_error(
    lines: list[bytes | bytearray | str], password: str
) -> ImapConnectionError:
    """
    Wyjątek dla odmowy LOGIN - rodzaj zależy od powodu podanego przez serwer.

    Limit jednoczesnych połączeń mija bez niczyjej interwencji, więc to
    zwykły `ImapConnectionError` (alert "ponowna próba za N minut").
    Każda inna odmowa to `ImapLoginRejectedError` - ponawianie jej nie
    naprawi i alert musi to powiedzieć.
    """
    message = _login_rejected_message(lines, password)
    if "TOO MANY" in _decode_server_lines(lines, secret=password).upper():
        return ImapConnectionError(message)
    return ImapLoginRejectedError(message)


def _login_rejected_message(lines: list[bytes | bytearray | str], password: str) -> str:
    """
    Komunikat o odrzuconym logowaniu Z POWODEM podanym przez serwer.

    Poprzednia wersja zawsze mówiła „sprawdź IMAP_USER i IMAP_PASS" -
    także wtedy, gdy Gmail odrzucał logowanie z zupełnie innego powodu
    (limit jednoczesnych połączeń, blokada bezpieczeństwa). Użytkownik
    zmieniał wtedy poprawne hasło i nic to nie dawało. Teraz komunikat
    niesie dosłowny powód z serwera, a podpowiedź pasuje do tego powodu.
    """
    reason = _decode_server_lines(lines, secret=password)
    normalized = reason.upper()

    if "TOO MANY" in normalized:
        hint = (
            "Serwer ogranicza liczbę jednoczesnych połączeń - hasło jest w porządku, "
            "spróbuj ponownie za kilka minut."
        )
    elif "APPLICATION-SPECIFIC PASSWORD" in normalized:
        hint = (
            "Gmail wymaga hasła aplikacji zamiast zwykłego hasła konta - wygeneruj je "
            "i wpisz jako IMAP_PASS w ~/ordly/backend/.env na Pi, potem zrestartuj usługę ordly."
        )
    elif "AUTHENTICATIONFAILED" in normalized or "INVALID CREDENTIALS" in normalized:
        hint = (
            "Login albo hasło aplikacji są nieprawidłowe. Hasło aplikacji Google przestaje "
            "działać m.in. po zmianie hasła do konta Google - wygeneruj nowe i wpisz je jako "
            "IMAP_PASS w ~/ordly/backend/.env na Pi, potem zrestartuj usługę ordly."
        )
    else:
        hint = (
            "Sprawdź IMAP_USER i IMAP_PASS w ~/ordly/backend/.env na Pi. Gmail i iCloud "
            "wymagają hasła aplikacji, nie zwykłego hasła konta."
        )

    prefix = f"Logowanie IMAP odrzucone: {reason}" if reason else "Logowanie IMAP odrzucone"
    return f"{prefix}. {hint}"


async def _close_quietly(client: aioimaplib.IMAP4) -> None:
    """
    Kończy sesję IMAP i zamyka gniazdo, nie rzucając wyjątków.

    Wołane w `finally` - błąd samego LOGOUT (np. timeout po zerwanym
    łączu) nie może przykryć pierwotnego błędu, który użytkownik ma
    zobaczyć. Gniazdo zamykamy dodatkowo ręcznie, bo LOGOUT w złym stanie
    protokołu (np. przed powitaniem serwera) kończy się wyjątkiem i nie
    zamyka połączenia.
    """
    with contextlib.suppress(*_IMAP_FAILURES):
        await client.logout()
    transport = getattr(client.protocol, "transport", None)
    if transport is not None and not transport.is_closing():
        transport.close()


def _format_imap_date(value: datetime) -> str:
    """Formatuje datę jako `09-Aug-2026` niezależnie od locale procesu."""
    return f"{value.day:02d}-{_IMAP_MONTHS[value.month - 1]}-{value.year}"


def _quote_for_imap(value: str) -> str:
    """
    Sprawdza, czy wartość wolno wstawić do komendy IMAP w cudzysłowie.

    Cudzysłów, backslash i znaki końca linii pozwoliłyby doczepić do
    komendy własne argumenty (odpowiednik SQL injection dla protokołu
    pocztowego). Message-ID zgodny z RFC nigdy ich nie zawiera, więc
    zamiast próbować je uciekać, odrzucamy taką wartość.
    """
    if any(character in value for character in ('"', "\\", "\r", "\n")):
        raise ValueError(f"Message-ID zawiera niedozwolone znaki: {value!r}")
    return value


async def _fetch_raw_message(client: aioimaplib.IMAP4, raw_id: bytes | str) -> bytes | None:
    """
    Pobiera surowe bajty jednej wiadomości po jej numerze w skrzynce.

    BODY.PEEK[] zamiast RFC822: obie komendy zwracaja te sama tresc, ale
    RFC822 (== BODY[]) ustawia na serwerze flage \\Seen, czyli oznaczalo
    uzytkownikowi maile jako przeczytane w Gmailu przy kazdej
    synchronizacji. Modul ma byc tylko-do-odczytu, wiec PEEK.
    """
    msg_num = raw_id.decode() if isinstance(raw_id, bytes) else str(raw_id)
    fetch_response = await client.fetch(msg_num, "(BODY.PEEK[])")
    if fetch_response.result != "OK":
        return None
    return _extract_message_bytes(fetch_response.lines)


def _extract_message_bytes(lines: list[bytes | bytearray]) -> bytes | None:
    """
    Wyciąga surowe bajty wiadomości z odpowiedzi FETCH.

    Odpowiedź to lista linii - krótkie to ramki protokołu IMAP
    (np. "1 FETCH (BODY[] {1234}", zamykający nawias), a najdłuższa
    to zawsze faktyczna treść maila.

    UWAGA na typ: aioimaplib zwraca ramki protokołu jako `bytes`, ale samą
    treść literału (czyli wiadomość) jako **`bytearray`** - a `bytearray`
    NIE jest instancją `bytes`. Wcześniejszy filtr `isinstance(line, bytes)`
    wycinał więc dokładnie tę jedną linię, po którą tu przychodzimy: każdy
    mail był po cichu pomijany, `sync` zawsze raportował "0 nowych", a
    aplikacja pokazywała pustą skrzynkę mimo poprawnego logowania IMAP.
    """
    candidates = [
        line for line in lines if isinstance(line, bytes | bytearray) and len(line) > 50
    ]
    if not candidates:
        return None
    return bytes(max(candidates, key=len))


def _decode_mime_header(raw_value: str | None) -> str:
    """
    Dekoduje nagłówek (`Subject`, `From`) do czytelnego tekstu.

    Białe znaki są na końcu ZWIJANE do pojedynczych spacji, bo serwery
    pocztowe łamią długie nagłówki na kilka linii (RFC 5322 "folding")
    i po zdekodowaniu zostaje w środku znak nowej linii. Realny temat
    z Allegro Lokalnie wyglądał tak: "Sprzedano 100szt. Butelka Gorilla
    10ml Liquid Aromat Baza olejki\\n\\n DIY kosmetyki PET" - i w takiej
    postaci trafiał na listę wiadomości oraz do dopasowywania wzorców.
    """
    if not raw_value:
        return ""
    parts: list[str] = []
    for part, encoding in decode_header(raw_value):
        if isinstance(part, bytes):
            parts.append(part.decode(encoding or "utf-8", errors="replace"))
        else:
            parts.append(part)
    return " ".join("".join(parts).split())


def _extract_body_preview(msg: Message) -> str:
    """
    Krótki, CZYSTO TEKSTOWY podgląd treści - to on trafia do bazy i na
    listę wiadomości.

    Poprzednia wersja przy mailu jednoczęściowym `text/html` (tak wysyła
    Allegro) wrzucała tutaj surowe źródło, więc na liście i w podglądzie
    widać było `<!DOCTYPE HTML ...` zamiast wiadomości. Teraz HTML jest
    najpierw sprowadzany do tekstu, a maile bez części `text/plain` nie
    dają już pustego podglądu.

    Część `text/plain` też nie jest tu przyjmowana na słowo: maile
    sprzedażowe z OLX mają w niej dosłowne `<a href="…">Potwierdź
    sprzedaż</a>`, bo szablon wkleja do wariantu tekstowego ten sam kod,
    co do HTML-owego. Gdy w „tekście" stoją znaczniki, przepuszczamy go
    przez ten sam konwerter - inaczej wróciłby ten sam objaw, tylko
    innymi drzwiami.
    """
    bodies = extract_bodies(msg)
    if bodies.text and bodies.text.strip():
        text = bodies.text.strip()
        if looks_like_markup(text):
            text = html_to_plain_text(text)
        return text[:_BODY_PREVIEW_LENGTH]
    if bodies.html:
        return html_to_plain_text(bodies.html)[:_BODY_PREVIEW_LENGTH]
    return ""


def _parse_email_date(raw_date: str | None) -> datetime:
    if not raw_date:
        return utc_now()
    try:
        parsed = email.utils.parsedate_to_datetime(raw_date)
    except (TypeError, ValueError):
        return utc_now()
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _parse_message(raw_bytes: bytes) -> MailMessage | None:
    """Mapuje surowe bajty RFC822 na MailMessage. Zwraca None, gdy brak Message-ID."""
    msg = email.message_from_bytes(raw_bytes)
    message_id = msg.get("Message-ID")
    if not message_id:
        return None
    sender = _decode_mime_header(msg.get("From"))
    return MailMessage(
        message_id=message_id.strip(),
        sender=sender,
        subject=_decode_mime_header(msg.get("Subject")),
        received_at=_parse_email_date(msg.get("Date")),
        source=classify_sender(sender),
        body_preview=_extract_body_preview(msg),
    )
