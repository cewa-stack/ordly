"""
Watcher IMAP - wykrywa nowe maile od skonfigurowanych nadawcow (Allegro/OLX).

Tylko-do-odczytu: wylacznie SEARCH + FETCH, nigdy nie usuwa ani nie
modyfikuje niczego na serwerze pocztowym.
"""

from __future__ import annotations

import email
import email.utils
from datetime import UTC, datetime
from email.header import decode_header
from email.message import Message

import aioimaplib

from app.domain.entities.mail_message import MailMessage
from app.infrastructure.mail.classify import classify_sender
from app.utils.time import utc_now

_BODY_PREVIEW_LENGTH = 500


class ImapConnectionError(Exception):
    """Połączenie, logowanie albo wyszukiwanie IMAP nie powiodło się."""


class ImapWatcher:
    """Odczytuje maile od skonfigurowanych nadawców przez IMAP (tylko odczyt)."""

    def __init__(self, host: str, port: int, user: str, password: str) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password

    async def fetch_new_from_senders(
        self, senders: list[str], since: datetime
    ) -> list[MailMessage]:
        """
        Zwraca maile od podanych nadawców, nadesłane od `since`.

        Jedno zapytanie SEARCH per nadawca - IMAP SEARCH nie wspiera
        czytelnie OR na wszystkich serwerach, więc bezpieczniej iterować.
        """
        try:
            client = aioimaplib.IMAP4_SSL(host=self._host, port=self._port)
            await client.wait_hello_from_server()
        except (OSError, TimeoutError, aioimaplib.Abort) as exc:
            # Nieosiągalny host/port albo zerwane TLS - bez tego opakowania
            # surowy OSError leciał do FastAPI jako 500 "Internal Server
            # Error" i użytkownik nie wiedział, że chodzi o pocztę.
            raise ImapConnectionError(
                f"Brak połączenia z serwerem IMAP {self._host}:{self._port} ({exc})"
            ) from exc

        login_response = await client.login(self._user, self._password)
        if login_response.result != "OK":
            raise ImapConnectionError(
                "Logowanie IMAP odrzucone - sprawdź IMAP_USER i IMAP_PASS w .env na Pi. "
                "Gmail i iCloud wymagają hasła aplikacji, nie zwykłego hasła konta."
            )

        select_response = await client.select("INBOX")
        if select_response.result != "OK":
            raise ImapConnectionError("Nie udało się otworzyć skrzynki INBOX")

        since_str = since.strftime("%d-%b-%Y")
        messages: list[MailMessage] = []
        seen_ids: set[str] = set()
        try:
            for sender in senders:
                search_response = await client.search(f'FROM "{sender}" SINCE {since_str}')
                if search_response.result != "OK" or not search_response.lines:
                    continue
                raw_ids = search_response.lines[0].split()
                for raw_id in raw_ids:
                    msg_num = raw_id.decode() if isinstance(raw_id, bytes) else str(raw_id)
                    fetch_response = await client.fetch(msg_num, "(RFC822)")
                    if fetch_response.result != "OK":
                        continue
                    raw_bytes = _extract_message_bytes(fetch_response.lines)
                    if raw_bytes is None:
                        continue
                    message = _parse_message(raw_bytes)
                    if message is None or message.message_id in seen_ids:
                        continue
                    seen_ids.add(message.message_id)
                    messages.append(message)
        finally:
            await client.logout()
        return messages


def _extract_message_bytes(lines: list[bytes]) -> bytes | None:
    """
    Wyciąga surowe bajty wiadomości z odpowiedzi FETCH.

    Odpowiedź to lista linii - krótkie to ramki protokołu IMAP
    (np. "1 FETCH (RFC822 {1234}", zamykający nawias), a najdłuższa
    to zawsze faktyczna treść maila.
    """
    candidates = [line for line in lines if isinstance(line, bytes) and len(line) > 50]
    if not candidates:
        return None
    return max(candidates, key=len)


def _decode_mime_header(raw_value: str | None) -> str:
    if not raw_value:
        return ""
    parts: list[str] = []
    for part, encoding in decode_header(raw_value):
        if isinstance(part, bytes):
            parts.append(part.decode(encoding or "utf-8", errors="replace"))
        else:
            parts.append(part)
    return "".join(parts)


def _extract_body_preview(msg: Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    charset = part.get_content_charset() or "utf-8"
                    text = payload.decode(charset, errors="replace")
                    return text.strip()[:_BODY_PREVIEW_LENGTH]
        return ""
    payload = msg.get_payload(decode=True)
    if not payload:
        return ""
    charset = msg.get_content_charset() or "utf-8"
    text = (
        payload.decode(charset, errors="replace")
        if isinstance(payload, bytes)
        else str(payload)
    )
    return text.strip()[:_BODY_PREVIEW_LENGTH]


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
