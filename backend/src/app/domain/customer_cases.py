"""
Rejestr anulowań i zwrotów pieniędzy - JEDEN rekord na zamówienie.

Pozycje z Notion (sekcja "Zwroty i anulowane zamówienia"):
"Brak automatycznego zbierania danych klientów po anulowaniu zamówienia
lub zwrocie pieniędzy", "Brak miejsca i jednolitego formatu dla danych
klientów po zwrotach", "Brak danych potrzebnych do późniejszego kontaktu
z klientem".

ZAKRES DANYCH (decyzja użytkownika D7 z 2026-10-04: "pomiń - niezgodne
z prawem"): rekord NIE przechowuje numeru telefonu, adresu e-mail ani
imienia i nazwiska kupującego. Klienta identyfikuje wyłącznie login
Allegro (Notion dopuszcza "imię i nazwisko klienta LUB login Allegro"),
a kontakt odbywa się przez Allegro, po numerze zamówienia.

Zasady rekordu:
- unikalny klucz (kanał, numer zamówienia) - ponowne wykrycie tego samego
  zamówienia aktualizuje rekord zamiast tworzyć duplikat;
- `merge_case` nigdy nie nadpisuje uzupełnionej wartości pustą;
- brak danej = None, w aplikacji "nieuzupełnione" - nigdy zgadywane
  wartości w rodzaju "nieznany";
- zmiana powodu trafia do historii (`CaseReasonChange`).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

# -------------------------------------------------------------- rodzaj sprawy
KIND_CANCELLATION = "CANCELLATION"
KIND_REFUND = "REFUND"
KIND_BOTH = "BOTH"

KIND_LABELS: dict[str, str] = {
    KIND_CANCELLATION: "Anulowanie zamówienia",
    KIND_REFUND: "Zwrot pieniędzy",
    KIND_BOTH: "Anulowanie i zwrot pieniędzy",
}

# ---------------------------------------------------------------------- powód
REASON_OUT_OF_STOCK = "OUT_OF_STOCK"
REASON_PAYMENT_PROBLEM = "PAYMENT_PROBLEM"
REASON_BUYER_RESIGNED = "BUYER_RESIGNED"
REASON_OTHER = "OTHER"

REASON_LABELS: dict[str, str] = {
    REASON_OUT_OF_STOCK: "Brak towaru",
    REASON_PAYMENT_PROBLEM: "Problem z płatnością",
    REASON_BUYER_RESIGNED: "Rezygnacja klienta",
    REASON_OTHER: "Inna",
}

#: Powód zwrotu podany przez kupującego w Allegro (`items[].reason.type`
#: w customer-returns) -> nasz powód. Kod z Allegro zostaje też w
#: `reason_detail`, więc nic się nie gubi. Nieznany kod -> "Inna".
_ALLEGRO_RETURN_REASONS: dict[str, str] = {
    "DONT_LIKE_IT": REASON_BUYER_RESIGNED,
    "MISTAKE": REASON_BUYER_RESIGNED,
    "BETTER_PRICE": REASON_BUYER_RESIGNED,
    "EXCESSIVE": REASON_BUYER_RESIGNED,
}

# ------------------------------------------------------------ status obsługi
HANDLING_REPORTED = "REPORTED"
HANDLING_IN_PROGRESS = "IN_PROGRESS"
HANDLING_DONE = "DONE"

HANDLING_LABELS: dict[str, str] = {
    HANDLING_REPORTED: "Zgłoszony",
    HANDLING_IN_PROGRESS: "W trakcie realizacji",
    HANDLING_DONE: "Zakończony",
}

# ------------------------------------------------------------ źródło zdarzenia
SOURCE_ALLEGRO_ORDER = "ALLEGRO_ORDER"
SOURCE_ALLEGRO_RETURN = "ALLEGRO_RETURN"
SOURCE_APP_STATUS = "APP_STATUS"
SOURCE_MIGRATION = "MIGRATION"

SOURCE_LABELS: dict[str, str] = {
    SOURCE_ALLEGRO_ORDER: "Allegro - anulowanie zamówienia",
    SOURCE_ALLEGRO_RETURN: "Allegro - zwrot klienta",
    SOURCE_APP_STATUS: "Status w aplikacji",
    SOURCE_MIGRATION: "Dane sprzed wdrożenia",
}

#: Źródło zmiany powodu w historii.
REASON_SOURCE_ALLEGRO = "allegro"
REASON_SOURCE_MANUAL = "manual"

#: Wartości, które marketplace wstawia zamiast brakującego loginu - to
#: "nieuzupełnione", a nie prawdziwy login.
_PLACEHOLDER_LOGINS = frozenset({"", "nieznany"})


def kind_label(kind: str) -> str:
    return KIND_LABELS.get(kind, kind)


def reason_label(reason: str | None) -> str:
    return REASON_LABELS.get(reason, reason) if reason else "nieuzupełnione"


def handling_label(status: str) -> str:
    return HANDLING_LABELS.get(status, status)


def source_label(source: str) -> str:
    return SOURCE_LABELS.get(source, source)


def clean_login(login: str | None) -> str | None:
    """Login albo None, gdy marketplace podał zaślepkę zamiast loginu."""
    if login is None or login.strip().lower() in _PLACEHOLDER_LOGINS:
        return None
    return login.strip()


def reason_from_allegro_return(reason_type: str | None) -> str | None:
    """Powód z kodu Allegro; brak kodu = nieuzupełnione (None)."""
    if not reason_type:
        return None
    return _ALLEGRO_RETURN_REASONS.get(reason_type.upper(), REASON_OTHER)


def combine_kinds(first: str, second: str) -> str:
    """Anulowanie + zwrot pieniędzy tego samego zamówienia = "oba zdarzenia"."""
    return first if first == second else KIND_BOTH


@dataclass(frozen=True, slots=True)
class CustomerCase:
    """
    Jeden rekord anulowania i/lub zwrotu pieniędzy.

    `id` = None dla rekordu jeszcze niezapisanego. Każde pole opcjonalne
    może być None = "nieuzupełnione".
    """

    marketplace: str
    order_external_id: str
    kind: str
    source: str
    handling_status: str = HANDLING_REPORTED
    allegro_order_id: str | None = None
    buyer_login: str | None = None
    order_date: datetime | None = None
    cancelled_at: datetime | None = None
    refunded_at: datetime | None = None
    reason: str | None = None
    reason_detail: str | None = None
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class CaseReasonChange:
    """Wpis historii powodu: kiedy, skąd, z czego na co."""

    case_id: int
    previous_reason: str | None
    new_reason: str | None
    source: str
    changed_at: datetime


def _keep[T](current: T | None, new: T | None) -> T | None:
    """Uzupełniona wartość zostaje; pusta przyjmuje nową."""
    return current if current is not None else new


def merge_case(existing: CustomerCase, incoming: CustomerCase) -> CustomerCase:
    """
    Łączy istniejący rekord z nowo wykrytym zdarzeniem.

    - pusta wartość nigdy nie nadpisuje uzupełnionej;
    - rodzaj sprawy sumuje się (anulowanie + zwrot = oba);
    - powód ustawiony już wcześniej (np. ręcznie) NIE jest nadpisywany
      powodem z Allegro - powód z Allegro uzupełnia tylko brak;
    - status obsługi i źródło zostają jak w istniejącym rekordzie.
    """

    return replace(
        existing,
        kind=combine_kinds(existing.kind, incoming.kind),
        allegro_order_id=_keep(existing.allegro_order_id, incoming.allegro_order_id),
        buyer_login=_keep(existing.buyer_login, incoming.buyer_login),
        order_date=_keep(existing.order_date, incoming.order_date),
        cancelled_at=_keep(existing.cancelled_at, incoming.cancelled_at),
        refunded_at=_keep(existing.refunded_at, incoming.refunded_at),
        reason=_keep(existing.reason, incoming.reason),
        reason_detail=_keep(existing.reason_detail, incoming.reason_detail),
    )


@dataclass(frozen=True, slots=True)
class CaseFilters:
    """Filtry listy rekordów (wszystkie opcjonalne, łączone przez AND)."""

    kinds: tuple[str, ...] = ()
    handling_status: str | None = None
    reason: str | None = None
    #: True = tylko rekordy bez powodu ("nieuzupełnione").
    reason_missing: bool = False
    source: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
