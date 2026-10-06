"""
Rozpoznawanie maila InPost „Potwierdzenie nadania przesyłki” dla paczki
OD HURTOWNI F.H.P. MAIK-POL - pozycja z Notion [FEAT-MAIL].

Mail przychodzi do skrzynki sklepu, gdy hurtownia nada paczkę do nas.
ORDLY ma wtedy raz poinformować (Control Hub + push na telefon), że paczka
jest w drodze - i nic więcej: nie przypisuje jej do zamówienia, nie zmienia
statusów, nie wymaga potwierdzenia.

Alert powstaje tylko, gdy spełnione są WSZYSTKIE warunki (W1-W7):

- adres nadawcy to dokładnie `info@paczkomaty.pl`, a wyświetlana nazwa
  to „InPost” (W1, W7 - inny nadawca z tym samym tekstem nie przechodzi);
- temat to dokładnie „InPost - Potwierdzenie nadania przesyłki” (W2);
- w treści jest jednoznaczny numer paczki (W3, W6);
- treść mówi, że paczka jest od F.H.P. MAIK-POL (W4, W5).

Wzorzec treści pochodzi z prawdziwego maila (zrzut w Notion, 2026-10-06):

    Poszło!
    Sprawy nabierają tempa. Twoja paczka od F.H.P. MAIK-POL wyruszyła
    w podróż do Ciebie.
    Numer paczki: 620999672171521435976372

Moduł niczego nie loguje i nie zapisuje - zwraca wynik, a decyzję
o logach i zapisie podejmuje `WholesaleParcelService`.
"""

from __future__ import annotations

import email.utils
import re
from dataclasses import dataclass

from app.domain.entities.mail_message import MailMessage
from app.domain.entities.wholesale_parcel import WholesaleParcelNotice
from app.infrastructure.mail.mime import MailBodies, html_to_plain_text

INPOST_SENDER_ADDRESS = "info@paczkomaty.pl"
INPOST_SENDER_NAME = "InPost"
SHIPMENT_CONFIRMATION_SUBJECT = "InPost - Potwierdzenie nadania przesyłki"
#: Jedyna obserwowana hurtownia (poza zakresem: inni hurtownicy).
WATCHED_WHOLESALER = "F.H.P. MAIK-POL"

OUTCOME_MATCH = "match"
OUTCOME_OTHER_SENDER = "other_sender"
OUTCOME_OTHER_SUBJECT = "other_subject"
OUTCOME_OTHER_WHOLESALER = "other_wholesaler"
OUTCOME_NO_NUMBER = "no_number"
OUTCOME_AMBIGUOUS_NUMBER = "ambiguous_number"

#: Numer paczki InPost to ciąg cyfr (w mailach 24 cyfry). Dopuszczamy
#: spacje wewnątrz numeru - niektóre szablony grupują cyfry.
_NUMBER = re.compile(r"numer\s+paczki\s*:?\s*(\d(?:[\d ]{8,38})\d)", re.IGNORECASE)
#: „Twoja paczka od <nadawca> wyruszyła…” - kto nadał paczkę.
_FROM_WHOM = re.compile(r"paczk\w*\s+od\s+(.{2,80}?)\s+wyruszy", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ParcelMailResult:
    """Wynik rozpoznania: `notice` tylko dla OUTCOME_MATCH."""

    outcome: str
    notice: WholesaleParcelNotice | None = None
    tracking_number: str | None = None
    wholesaler: str | None = None

    @property
    def is_match(self) -> bool:
        return self.outcome == OUTCOME_MATCH


def is_inpost_shipment_header(message: MailMessage) -> bool:
    """
    Szybki filtr po samych nagłówkach (nadawca + temat) - zanim ORDLY
    dociągnie pełną treść maila osobnym połączeniem IMAP.
    """
    return _sender_ok(message.sender) and _subject_ok(message.subject)


def parse_parcel_mail(message: MailMessage, bodies: MailBodies | None) -> ParcelMailResult:
    """Rozpoznaje mail - patrz docstring modułu."""
    if not _sender_ok(message.sender):
        return ParcelMailResult(OUTCOME_OTHER_SENDER)
    if not _subject_ok(message.subject):
        return ParcelMailResult(OUTCOME_OTHER_SUBJECT)

    text = _plain_text(message, bodies)

    wholesaler = _wholesaler(text)
    if wholesaler is None or _normalize(wholesaler) != _normalize(WATCHED_WHOLESALER):
        return ParcelMailResult(OUTCOME_OTHER_WHOLESALER, wholesaler=wholesaler)

    numbers = {match.replace(" ", "") for match in _NUMBER.findall(text)}
    if not numbers:
        return ParcelMailResult(OUTCOME_NO_NUMBER, wholesaler=wholesaler)
    if len(numbers) > 1:
        return ParcelMailResult(OUTCOME_AMBIGUOUS_NUMBER, wholesaler=wholesaler)
    tracking_number = numbers.pop()

    return ParcelMailResult(
        OUTCOME_MATCH,
        notice=WholesaleParcelNotice(
            message_id=message.message_id,
            tracking_number=tracking_number,
            wholesaler_name=WATCHED_WHOLESALER,
            received_at=message.received_at,
        ),
        tracking_number=tracking_number,
        wholesaler=wholesaler,
    )


def _sender_ok(sender: str) -> bool:
    name, address = email.utils.parseaddr(sender)
    return (
        address.strip().lower() == INPOST_SENDER_ADDRESS
        and " ".join(name.split()).casefold() == INPOST_SENDER_NAME.casefold()
    )


def _subject_ok(subject: str) -> bool:
    return " ".join(subject.split()).casefold() == SHIPMENT_CONFIRMATION_SUBJECT.casefold()


def _plain_text(message: MailMessage, bodies: MailBodies | None) -> str:
    """
    Treść jako jeden ciąg z pojedynczymi spacjami. Wariant HTML ma
    pierwszeństwo (tak wygląda mail na zrzucie), tekstowy i podgląd z bazy
    są zapasem. Zwinięcie białych znaków łączy „MAIK-” i „POL”, gdyby
    szablon złamał nazwę na dwie linie.
    """
    parts: list[str] = []
    if bodies is not None and bodies.html:
        parts.append(html_to_plain_text(bodies.html))
    if bodies is not None and bodies.text:
        parts.append(bodies.text)
    if not parts:
        parts.append(message.body_preview)
    return " ".join(" ".join(parts).split())


def _wholesaler(text: str) -> str | None:
    match = _FROM_WHOM.search(text)
    return match.group(1).strip() if match else None


def _normalize(name: str) -> str:
    """Porównanie nazwy firmy bez wielkości liter, spacji i myślników łamanych."""
    return re.sub(r"[\s\-‐-―]", "", name).casefold()
