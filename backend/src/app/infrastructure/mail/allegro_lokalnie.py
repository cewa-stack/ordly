"""
Rozpoznawanie zdarzeń Allegro Lokalnie z powiadomień e-mail.

Allegro Lokalnie **nie ma publicznego API** (Allegro potwierdziło, że nie
planuje go udostępnić), a web scraping panelu łamałby regulamin i groził
blokadą konta. Jedynym stabilnym, oficjalnym kanałem zdarzeń zostaje
poczta: serwis wysyła powiadomienie przy sprzedaży, wiadomości od
kupującego, pytaniu o dostawę i doręczeniu paczki.

Ten moduł NIE otwiera własnego połączenia IMAP - maile z
`@allegrolokalnie.pl` pobiera ten sam watcher, co pozostałą pocztę
(`imap_watcher.py`), a rozróżnienie kanału robi `classify_sender`.
Tutaj zostaje wyłącznie rozpoznanie, CO się wydarzyło.

WZORCE SĄ ZWERYFIKOWANE NA REALNYCH MAILACH - komplet próbek leży
w `tests/fixtures/allegro_lokalnie/` i każda z nich ma swój test.
Pierwsza wersja tego modułu zgadywała brzmienie szablonów i myliła się
w połowie przypadków: dopasowywała m.in. `"kup teraz"`, które okazało się
GENERYCZNĄ ETYKIETĄ typu ogłoszenia obecną w każdym mailu - przez co
wiadomość od kupującego i doręczenie paczki lądowały jako "nowe
zamówienie". Stąd dwie zasady poniżej:

1. **Klasyfikacja idzie po TEMACIE**, nie po treści. Treść jest pełna
   stałych napisów interfejsu ("kup teraz", "PRZEJDŹ DO ROZMOWY",
   "Zamówienia od kupujących"), które nie mówią nic o zdarzeniu.
2. **Nierozpoznany szablon daje `unknown`, a nie zgadywanie.** Allegro
   może zmienić brzmienie maila bez ostrzeżenia - wtedy zdarzenie ma
   stracić etykietę, ale NIE zniknąć.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from decimal import Decimal, InvalidOperation

from app.domain.entities.allegro_lokalnie_event import (
    EVENT_INTEREST,
    EVENT_NEW_MESSAGE,
    EVENT_NEW_ORDER,
    EVENT_ORDER_STATUS,
    EVENT_RETURN,
    EVENT_UNKNOWN,
    AllegroLokalnieEvent,
)
from app.domain.entities.mail_message import MailMessage
from app.infrastructure.mail.mime import MailBodies, html_to_plain_text

#: Wzorce TEMATU, w kolejności priorytetu. Pierwsza pozycja każdej grupy
#: pochodzi wprost z próbki w `tests/fixtures/allegro_lokalnie/`, reszta
#: to warianty tego samego zdarzenia, których jeszcze nie widzieliśmy na
#: żywo - dopisane, bo są tanie, a ich brak kosztowałby przeoczoną
#: sprzedaż.
_SUBJECT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        EVENT_NEW_ORDER,
        (
            "sprzedano",  # "Sprzedano 25szt. Butelka Gorilla 60ml…"
            "kupil przedmiot",
            "kupila przedmiot",
            "nowe zamowienie",
            "oplacone zamowienie",
            "zamowienie oplacone",
        ),
    ),
    (
        # Zwrot STOI PRZED `EVENT_ORDER_STATUS`, bo to też zmiana
        # zamówienia - gdyby był niżej, wpadłby w ogólniejszą grupę.
        # UWAGA: żadna z próbek w `tests/fixtures/allegro_lokalnie/` nie
        # jest zwrotem (mamy sprzedaż, wiadomość, pytanie o dostawę i
        # doręczenie paczki), więc dokładne brzmienie tematu maila
        # o zwrocie jest NIEPOTWIERDZONE. Wzorzec "zwrot" był tu już
        # wcześniej - w grupie `EVENT_ORDER_STATUS` - i to jego jedyną
        # zmianą jest teraz trafniejsza etykieta: temat ze słowem
        # „zwrot" nigdy nie oznacza doręczonej paczki. Jeśli Allegro
        # Lokalnie nazywa te maile inaczej, zdarzenie wpadnie w
        # `order_status` albo `unknown` - czyli tak jak dotąd, bez
        # regresu. Po pierwszej realnej próbce dopisz ją do fixtures
        # i uzupełnij wzorce.
        EVENT_RETURN,
        (
            "zwrot",
            "reklamacj",
        ),
    ),
    (
        EVENT_ORDER_STATUS,
        (
            "dostarczylismy twoja paczke",  # "Dostarczyliśmy Twoją paczkę z…"
            "paczka dotarla",
            "anulowa",
            "status zamowienia",
        ),
    ),
    (
        EVENT_NEW_MESSAGE,
        (
            "nowa wiadomosc",  # "Nowa wiadomość do 5szt. Butelka Gorilla…"
            "napisal do ciebie",
            "napisala do ciebie",
            "masz wiadomosc",
        ),
    ),
    (
        EVENT_INTEREST,
        (
            "prosi o warunki dostawy",  # "Kupujący prosi o warunki dostawy…"
            "chce kupic",
            "zainteresowan",
            "pyta o ogloszenie",
        ),
    ),
)

#: Etykieta typu ogłoszenia, po której w treści ZAWSZE stoi jego tytuł.
#: Sprawdzone na wszystkich ośmiu próbkach.
_LISTING_MARKERS = ("kup teraz", "licytacja", "oferta")

#: Nagłówek sekcji z kwotą faktycznie zapłaconą przez kupującego.
_TOTAL_MARKER = "laczna kwota zakupu"

#: Nagłówek sekcji z danymi kupującego: "login (Imię Nazwisko)".
_BUYER_MARKER = "osoba kupujaca"

#: Kwota: `129 zł`, `1 299,00 zł`, `49.90 PLN`. Separator tysięcy bywa
#: zwykłą albo niełamliwą spacją - obie wersje muszą przejść.
_AMOUNT = re.compile(
    r"(\d{1,3}(?:[\s\u00a0]\d{3})*|\d+)(?:[.,](\d{1,2}))?\s*(?:z[łl]|PLN)",
    re.IGNORECASE,
)

#: Link do transakcji w mailu sprzedażowym - jedyny stabilny numer, jaki
#: Allegro Lokalnie w ogóle podaje. W mailach niesprzedażowych go nie ma.
_TRANSACTION_LINK = re.compile(
    r"allegrolokalnie\.pl/konto/oferty/transakcja/([0-9a-f-]{36})", re.IGNORECASE
)

#: "login (Imię Nazwisko)" - tak Allegro podaje kupującego w sekcji
#: "Osoba kupująca".
_BUYER_PARTS = re.compile(r"^(.+?)\s*\(([^)]+)\)\s*$")

#: Liczba sztuk: "1 sztuka", "4 sztuki", "12 sztuk".
_QUANTITY = re.compile(r"\b(\d+)\s+sztuk", re.IGNORECASE)

#: `ł` (U+0142) to OSOBNY znak Unicode, nie "l ze znakiem diakrytycznym",
#: więc NFKD go nie rozkłada - w przeciwieństwie do ą, ę, ó, ś, ć, ń, ź, ż.
#: Bez tej podmianki wzorzec "laczna" nigdy nie trafiłby w "Łączna".
_MANUAL_FOLD = str.maketrans({"ł": "l", "Ł": "L"})


def parse_event(
    message: MailMessage, bodies: MailBodies | None = None
) -> AllegroLokalnieEvent:
    """
    Rozpoznaje zdarzenie w powiadomieniu z Allegro Lokalnie.

    Nigdy nie rzuca wyjątku i nigdy nie zwraca `None` - nietypowy mail
    dostaje typ `unknown`, a nie znika. Job synchronizacji skrzynki
    chodzi w tle co 5 minut i jeden dziwny szablon nie może go zatrzymać.

    Args:
        message: Mail zapisany w skrzynce, sklasyfikowany jako pochodzący
            z Allegro Lokalnie.
        bodies: Pełna treść maila (HTML + tekst). Warto ją podać:
            `message.body_preview` jest przycięty do 500 znaków, a sekcje
            "Łączna kwota zakupu" i "Osoba kupująca" stoją w szablonie
            NIŻEJ. Numer transakcji siedzi WYŁĄCZNIE w HTML-u (w adresie
            linku), więc bez pełnej treści zdarzenie nie stanie się
            zamówieniem - zostanie zwykłym powiadomieniem.

    Returns:
        Rozpoznane zdarzenie - z typem `unknown`, gdy szablon jest nieznany.
    """
    subject = _collapse(message.subject)
    text = _text_of(bodies) or message.body_preview
    html = bodies.html if bodies is not None else None
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    unit_amount = _amount_after(lines, _listing_index(lines), skip=1)
    total_amount = _amount_after(lines, _marker_index(lines, _TOTAL_MARKER))
    buyer_login, buyer_name = _buyer(lines)

    return AllegroLokalnieEvent(
        message_id=message.message_id,
        event_type=_classify(subject, text),
        subject=subject,
        snippet=lines[0] if lines else "",
        received_at=message.received_at,
        listing_title=_listing_title(lines),
        buyer_login=buyer_login,
        buyer_name=buyer_name,
        quantity=_quantity(lines),
        unit_amount=unit_amount,
        amount=total_amount or unit_amount,
        transaction_id=_transaction_id(html),
    )


def _text_of(bodies: MailBodies | None) -> str:
    """Treść maila jako tekst - z części tekstowej albo z HTML-a."""
    if bodies is None:
        return ""
    if bodies.text and bodies.text.strip():
        return bodies.text
    return html_to_plain_text(bodies.html) if bodies.html else ""


def _transaction_id(html: str | None) -> str | None:
    """Numer transakcji z linku „Sprawdź szczegóły" - tylko w mailach sprzedażowych."""
    if not html:
        return None
    match = _TRANSACTION_LINK.search(html)
    return match.group(1).lower() if match else None


def offer_external_id(listing_title: str) -> str:
    """
    Stabilny identyfikator oferty Allegro Lokalnie, wyliczony z tytułu.

    Allegro Lokalnie NIE podaje w mailu numeru ogłoszenia - w treści jest
    tylko jego tytuł. Skrót z tytułu daje identyfikator, który:

    - jest ten sam dla każdej kolejnej sprzedaży tego ogłoszenia, więc
      raz ustawione powiązanie z magazynem działa dalej,
    - mieści się w kolumnie `offer_links.external_product_id` (100 znaków),
      czego pełny tytuł nie gwarantuje,
    - da się go wpisać ręcznie w `/stock link`, w przeciwieństwie do
      stukilkudziesięcioznakowej nazwy.

    OGRANICZENIE, którego nie da się obejść bez API: zmiana tytułu
    ogłoszenia na Allegro Lokalnie tworzy NOWY identyfikator, więc
    powiązanie z magazynem trzeba ustawić ponownie. Objawi się to
    powiadomieniem „Sprzedaż poza magazynem" przy pierwszej sprzedaży po
    zmianie - czyli głośno, a nie po cichu.
    """
    normalized = " ".join(listing_title.lower().split())
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
    return f"al:{digest}"


def _classify(subject: str, text: str) -> str:
    """
    Rozpoznaje typ zdarzenia - najpierw po temacie, potem po treści.

    Treść jest tylko planem awaryjnym dla maila z pustym albo
    nieczytelnym tematem, i celowo sprawdzana WYŁĄCZNIE wzorcami
    tematowymi - napisy interfejsu z szablonu nie biorą udziału
    w rozstrzyganiu.
    """
    for haystack in (_normalize(subject), _normalize(text)):
        for candidate, patterns in _SUBJECT_RULES:
            if any(pattern in haystack for pattern in patterns):
                return candidate
    return EVENT_UNKNOWN


def _normalize(text: str) -> str:
    """Sprowadza tekst do postaci bez polskich znaków i wielkości liter."""
    folded = unicodedata.normalize("NFKD", text.lower().translate(_MANUAL_FOLD))
    return "".join(character for character in folded if not unicodedata.combining(character))


def _collapse(text: str) -> str:
    """Zwija białe znaki - temat maila bywa złamany na kilka linii przez serwer."""
    return " ".join(text.split())


def _marker_index(lines: list[str], marker: str) -> int | None:
    """Numer linii zaczynającej się od podanego nagłówka sekcji."""
    for index, line in enumerate(lines):
        if _normalize(line).startswith(marker):
            return index
    return None


def _listing_index(lines: list[str]) -> int | None:
    """
    Numer linii z etykietą typu ogłoszenia ("kup teraz").

    Zaraz po niej stoi tytuł ogłoszenia - to najstabilniejsza kotwica
    w całym szablonie, wspólna dla wszystkich czterech typów maili.
    """
    for index, line in enumerate(lines):
        if _normalize(line) in _LISTING_MARKERS:
            return index
    return None


def _listing_title(lines: list[str]) -> str | None:
    """Tytuł ogłoszenia - pierwsza linia po etykiecie typu ogłoszenia."""
    index = _listing_index(lines)
    if index is None or index + 1 >= len(lines):
        return None
    title = lines[index + 1]
    # Zabezpieczenie przed szablonem, w którym po etykiecie od razu stoi
    # kwota - wtedy tytułu po prostu nie ma, zamiast fałszywej "49,99 zł".
    return None if _AMOUNT.fullmatch(title) else title


def _amount_after(lines: list[str], index: int | None, skip: int = 0) -> Decimal | None:
    """Pierwsza kwota w liniach po podanym indeksie (`skip` linii pominiętych)."""
    if index is None:
        return None
    for line in lines[index + 1 + skip :]:
        parsed = _parse_amount(line)
        if parsed is not None:
            return parsed
    return None


def _parse_amount(text: str) -> Decimal | None:
    """Wyciąga kwotę z linii; `None`, gdy jej tam nie ma albo jest niepoprawna."""
    match = _AMOUNT.search(text)
    if match is None:
        return None
    integer_part = re.sub(r"[\s\u00a0]", "", match.group(1))
    fraction = match.group(2) or "0"
    try:
        return Decimal(f"{integer_part}.{fraction.ljust(2, '0')}")
    except InvalidOperation:
        return None


def _quantity(lines: list[str]) -> int | None:
    """
    Liczba sprzedanych sztuk - szukana tylko w okolicy ogłoszenia.

    Dalej w mailu pojawiają się inne liczby ze słowem "sztuk"
    (np. w regulaminowej stopce), więc przeszukiwanie całości dawałoby
    przypadkowe trafienia.
    """
    index = _listing_index(lines)
    if index is None:
        return None
    for line in lines[index : index + 6]:
        match = _QUANTITY.search(line)
        if match is not None:
            return int(match.group(1))
    return None


def _buyer(lines: list[str]) -> tuple[str | None, str | None]:
    """
    Kupujący jako `(login, imię i nazwisko)`.

    W mailach sprzedażowych stoi w sekcji "Osoba kupująca" jako
    `Antek2034 (Antoni Ponieważ)` - login pierwszy. W wiadomościach od
    kupującego tej sekcji nie ma, a linia zdarzenia ma KOLEJNOŚĆ ODWROTNĄ:
    "Masz nową wiadomość od Piotr (DARROK)" - imię pierwsze. Stąd dwa
    osobne podejścia zamiast jednego wzorca.
    """
    index = _marker_index(lines, _BUYER_MARKER)
    if index is not None and index + 1 < len(lines):
        match = _BUYER_PARTS.match(lines[index + 1])
        if match is not None:
            return match.group(1).strip(), match.group(2).strip()
        return lines[index + 1], None

    for line in lines[:8]:
        match = re.search(r"\bod\s+(.+?)\s*\(([^)]+)\)", line)
        if match is not None:
            return match.group(2).strip(), match.group(1).strip()
    return None, None
