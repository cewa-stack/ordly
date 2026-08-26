"""
Odczytywanie powiadomień e-mail z Allegro.pl (`powiadomienia@allegro.pl`).

Allegro.pl MA API i ORDLY z niego korzysta - zamówienia, zwroty i wątki
dyskusji przychodzą stamtąd. Dlatego z poczty czytamy tu **jedną rzecz**:
informację o ROZPOCZĘTEJ DYSKUSJI. Powód jest konkretny:

- ORDLY odpytuje `/sale/issues` tylko wtedy, gdy otworzysz ekran Dyskusji,
  więc bez maila o nowej dyskusji dowiadujesz się dopiero, gdy sam
  zajrzysz;
- termin „jeśli nie wypowiesz się do…", po którym Allegro włącza się do
  rozmowy, jest WYŁĄCZNIE w mailu - API go nie zwraca.

Czego tu świadomie NIE ma:

- **zwrotów** - `SyncOrdersService._sync_customer_returns` pobiera je
  z API i publikuje `OrderReturnCreated`, które już wysyła powiadomienie.
  Drugi tor z poczty dałby użytkownikowi dwa powiadomienia o jednym
  zwrocie;
- **zamówień** - to samo, `OrderCreated` idzie z synchronizacji API.

Wzorce sprawdzone na realnym mailu: `tests/fixtures/allegro_mail/`.
"""

from __future__ import annotations

import re
from datetime import datetime

from app.domain.entities.dispute_notice import DisputeNotice
from app.domain.entities.mail_message import MailMessage
from app.infrastructure.mail.mime import MailBodies, html_to_plain_text

#: Zdanie z treści maila o rozpoczęciu dyskusji. Temat („Dyskusja - X
#: zgłosił problem z zamówieniem") też by wystarczył, ale Allegro używa
#: słowa „Dyskusja" również w mailach o KOLEJNYCH wiadomościach w już
#: trwającym wątku - a te nie są nowym zdarzeniem.
_DISPUTE_OPENED = re.compile(r"rozpocz[ąa][łl]\s+z\s+Tob[ąa]\s+dyskusj", re.IGNORECASE)

#: Link „Przejdź do dyskusji" - stąd identyfikator wątku.
_ISSUE_LINK = re.compile(
    r"allegro\.pl/moje-allegro/sprzedaz/dyskusje/([0-9a-f-]{36})", re.IGNORECASE
)

#: Link do profilu kupującego - najstabilniejsze źródło jego loginu.
_BUYER_LINK = re.compile(r"allegro\.pl/uzytkownik/([A-Za-z0-9._-]+)", re.IGNORECASE)

#: „zakupu z 20.07.2026 deeb2fc0-8419-11f1-bed3-7de93eca4a57"
_ORDER_ID = re.compile(r"zakupu z\s+[\d.]+\s+([0-9a-f-]{36})", re.IGNORECASE)

#: „Jeśli nie wypowiesz się do 29.07.2026 08:41 (CEST)"
_RESPOND_BY = re.compile(
    r"nie wypowiesz si[ęe]\s+do\s+(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2})",
    re.IGNORECASE,
)

#: Nagłówek sekcji, po którym stoi powód zgłoszony przez kupującego.
_REASON_HEADING = "powod"

#: Nazwa oferty stoi w linii z identyfikatorem w nawiasie:
#: „50x Butelki PET 30ml…(18752263792)".
_OFFER_LINE = re.compile(r"^(.*\S)\s*\((\d{6,})\)\s*$")


def parse_dispute_notice(
    message: MailMessage, bodies: MailBodies | None = None
) -> DisputeNotice | None:
    """
    Rozpoznaje mail o rozpoczęciu dyskusji i wyciąga z niego dane.

    Returns:
        `DisputeNotice`, gdy to mail o NOWEJ dyskusji i da się z niego
        odczytać identyfikator wątku. W każdym innym przypadku `None` -
        czyli mail zostaje zwykłą pozycją w skrzynce, bez powiadomienia.
        `None` nie jest błędem: większość poczty z Allegro.pl to
        zdarzenia, o których ORDLY wie już z API.

    Nigdy nie rzuca wyjątku - job skrzynki chodzi w tle co 5 minut
    i jeden nietypowy szablon nie może go zatrzymać.
    """
    html = bodies.html if bodies is not None else None
    text = _text_of(bodies) or message.body_preview
    if not _DISPUTE_OPENED.search(text):
        return None

    issue_id = _first_group(_ISSUE_LINK, html)
    if issue_id is None:
        # Bez identyfikatora wątku powiadomienie nie miałoby dokąd
        # prowadzić, a „masz nową dyskusję, poszukaj jej sam" jest gorsze
        # niż pozycja w skrzynce.
        return None

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return DisputeNotice(
        message_id=message.message_id,
        issue_id=issue_id.lower(),
        buyer_login=_first_group(_BUYER_LINK, html) or _buyer_from_text(text) or "kupujący",
        received_at=message.received_at,
        order_external_id=_first_group(_ORDER_ID, text),
        offer_name=_offer_name(lines),
        reason=_reason(lines),
        respond_by=_respond_by(text),
    )


def _text_of(bodies: MailBodies | None) -> str:
    """Treść maila jako tekst - z części tekstowej albo z HTML-a."""
    if bodies is None:
        return ""
    if bodies.text and bodies.text.strip():
        return bodies.text
    return html_to_plain_text(bodies.html) if bodies.html else ""


def _first_group(pattern: re.Pattern[str], haystack: str | None) -> str | None:
    if not haystack:
        return None
    match = pattern.search(haystack)
    return match.group(1) if match else None


def _buyer_from_text(text: str) -> str | None:
    """Login z linii „kupujący Rexpiot właśnie rozpoczął…" - plan awaryjny."""
    match = re.search(r"kupuj[ąa]cy\s+(\S+)\s+w[łl]a[śs]nie\s+rozpocz", text, re.IGNORECASE)
    return match.group(1) if match else None


def _offer_name(lines: list[str]) -> str | None:
    """Nazwa oferty - linia zakończona identyfikatorem w nawiasie."""
    for line in lines:
        match = _OFFER_LINE.match(line)
        if match is not None:
            return match.group(1)
    return None


def _reason(lines: list[str]) -> str | None:
    """Powód zgłoszenia - linia zaraz po nagłówku „Powód"."""
    for index, line in enumerate(lines):
        if _fold(line) == _REASON_HEADING and index + 1 < len(lines):
            return lines[index + 1]
    return None


def _respond_by(text: str) -> datetime | None:
    """
    Termin odpowiedzi. Zwracany jako czas lokalny bez strefy - mail podaje
    go w czasie polskim, a cała aplikacja i tak operuje na czasie lokalnym Pi.
    """
    match = _RESPOND_BY.search(text)
    if match is None:
        return None
    day, month, year, hour, minute = (int(part) for part in match.groups())
    try:
        return datetime(year, month, day, hour, minute)
    except ValueError:
        return None


def _fold(text: str) -> str:
    """Do porównań nagłówków: bez ogonków, bez wielkości liter."""
    table = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
    return text.translate(table).strip().lower()
