"""
Rozpoznawanie zdarzeń OLX z powiadomień e-mail.

OLX nie udostępnia samoobsługowego API dla sprzedawców (patrz
`files/appplans_05_olx_integration.md`), a scraping panelu łamałby
regulamin. Tak jak przy Allegro Lokalnie zostaje więc poczta.

WZORCE SĄ ZWERYFIKOWANE NA REALNYCH MAILACH - próbki leżą
w `tests/fixtures/olx/` i każda ma swój test. Dwie zasady, te same co
w `allegro_lokalnie.py` i z tego samego powodu (pierwsza wersja tamtego
modułu zgadywała szablony i myliła się w połowie przypadków):

1. **Klasyfikacja idzie po TEMACIE**, nie po treści. Treść jest pełna
   stałych napisów interfejsu („Zobacz wiadomość i odpowiedz",
   „Potwierdź sprzedaż", cała sekcja o pakowaniu paczki), które nie
   mówią nic o zdarzeniu.
2. **Nierozpoznany szablon daje `unknown`, a nie zgadywanie.** OLX może
   zmienić brzmienie maila bez ostrzeżenia - wtedy zdarzenie ma stracić
   etykietę, ale NIE zniknąć.

CZEGO W MAILU SPRZEDAŻOWYM OLX NIE MA - i to jest najważniejsza rzecz
w tym module. Sprawdzone na obu próbkach, w części tekstowej i w HTML-u:

- **kwoty.** Ani ceny ogłoszenia, ani sumy zapłaconej przez kupującego.
  Mail mówi wyłącznie „Płatność została dokonana".
- **liczby sztuk.** Przesyłka OLX to jedna transakcja na jedno
  ogłoszenie; liczby widoczne w tytułach („5x Butelka…", „20 szt.") są
  częścią NAZWY ogłoszenia, a nie ilością w tej sprzedaży.
- **kupującego.** Ani loginu, ani imienia.

Jest za to komplet tego, co pozwala rozpoznać, CO się sprzedało:
tytuł ogłoszenia i UUID transakcji z linku „Potwierdź sprzedaż".
Konsekwencje dla tworzenia zamówień opisuje `services/olx_orders_service.py`.
"""

from __future__ import annotations

import re
import unicodedata

from app.domain.entities.mail_message import MailMessage
from app.domain.entities.olx_event import (
    EVENT_NEW_MESSAGE,
    EVENT_NEW_ORDER,
    EVENT_RETURN,
    EVENT_UNKNOWN,
    OlxEvent,
)
from app.infrastructure.mail.mime import MailBodies, html_to_plain_text

#: Wzorce TEMATU, w kolejności priorytetu. Pierwsza pozycja każdej grupy
#: pochodzi wprost z próbki w `tests/fixtures/olx/`, reszta to warianty
#: tego samego zdarzenia, których jeszcze nie widzieliśmy na żywo -
#: dopisane, bo są tanie, a ich brak kosztowałby przeoczoną sprzedaż.
_SUBJECT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        EVENT_NEW_ORDER,
        (
            # "💵➡️👍 Kupujący już zapłacił, potwierdź sprzedaż do 15:29 16-12-2025"
            "potwierdz sprzedaz",
            "kupujacy juz zaplacil",
            "przedmiot zostal kupiony",
            "sprzedales przedmiot",
        ),
    ),
    (
        # Grupa BEZ ani jednej zweryfikowanej próbki - w przekazanych
        # mailach nie ma zwrotu ani reklamacji z OLX. Wzorce poniżej są
        # nieoczywistym wyjątkiem od zasady „nie zgaduj": słowa „zwrot"
        # i „reklamacja" w temacie maila nie mają innego znaczenia niż
        # to jedno, więc fałszywe trafienie jest praktycznie niemożliwe.
        # Gdyby OLX nazywał te maile inaczej, wpadną w `unknown` - czyli
        # dalej dostaniesz powiadomienie, tylko z neutralnym tytułem.
        # Po pierwszej realnej próbce dopisz ją do fixtures.
        EVENT_RETURN,
        (
            "zwrot",
            "reklamacj",
        ),
    ),
    (
        EVENT_NEW_MESSAGE,
        (
            "wiadomosci dotyczace ogloszen",  # temat maila, zawsze ten sam
            "wiadomosc do ogloszenia",  # tytuł HTML tego samego maila
            "czeka na ciebie wiadomosc",
        ),
    ),
)

#: Tytuł ogłoszenia w mailu sprzedażowym: `Twój przedmiot „TYTUŁ” został
#: kupiony.` Cudzysłowy to polskie „ (U+201E) i ” (U+201D); wariant
#: z prostym `"` jest na wypadek zmiany szablonu.
_SALE_TITLE = re.compile(r"przedmiot\s+[„\"](.+?)[”\"]", re.DOTALL)

#: Tytuł ogłoszenia w mailu z wiadomością: `Czeka na Ciebie wiadomość do
#: ogłoszenia: TYTUŁ` (nagłówek treści) albo `Wiadomość do ogłoszenia:
#: "TYTUŁ"` (tytuł HTML). Obie formy stoją w tej samej wiadomości.
_MESSAGE_TITLE = re.compile(r"og[łl]oszenia:\s*[„\"]?(.+?)[”\"]?\s*$", re.IGNORECASE)

#: UUID transakcji z linku „Potwierdź sprzedaż"
#: (`delivery.olx.pl/orders/sales/{uuid}`). Jedyny stabilny numer, jaki
#: OLX podaje w mailu - ten sam link bez UUID-a występuje w treści kilka
#: razy, dlatego wzorzec WYMAGA identyfikatora, zamiast dopasowywać samą
#: ścieżkę.
_ORDER_LINK = re.compile(
    r"delivery\.olx\.pl/orders/sales/"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)

#: `ł` (U+0142) to OSOBNY znak Unicode, nie "l ze znakiem diakrytycznym",
#: więc NFKD go nie rozkłada - w przeciwieństwie do ą, ę, ó, ś, ć, ń, ź, ż.
#: Bez tej podmianki wzorzec "ogloszen" nigdy nie trafiłby w "ogłoszeń".
_MANUAL_FOLD = str.maketrans({"ł": "l", "Ł": "L"})


def parse_event(message: MailMessage, bodies: MailBodies | None = None) -> OlxEvent:
    """
    Rozpoznaje zdarzenie w powiadomieniu z OLX.

    Nigdy nie rzuca wyjątku i nigdy nie zwraca `None` - nietypowy mail
    dostaje typ `unknown`, a nie znika. Job synchronizacji skrzynki
    chodzi w tle co 5 minut i jeden dziwny szablon nie może go zatrzymać.

    Args:
        message: Mail zapisany w skrzynce, sklasyfikowany jako OLX.
        bodies: Pełna treść maila (HTML + tekst). Warto ją podać:
            `message.body_preview` jest przycięty do 500 znaków, a UUID
            transakcji siedzi WYŁĄCZNIE w HTML-u (w adresie linku) -
            bez pełnej treści sprzedaż nie ma identyfikatora i zostanie
            zwykłym powiadomieniem.

    Returns:
        Rozpoznane zdarzenie - z typem `unknown`, gdy szablon jest nieznany.
    """
    subject = _collapse(message.subject)
    html = bodies.html if bodies is not None else None
    lines = _content_lines(bodies, message)
    event_type = _classify(subject, "\n".join(lines))

    return OlxEvent(
        message_id=message.message_id,
        event_type=event_type,
        subject=subject,
        snippet=lines[0] if lines else "",
        received_at=message.received_at,
        listing_title=_listing_title(lines, event_type),
        # UUID siedzi w ADRESIE linku, więc szukamy go w surowym HTML-u -
        # konwersja na tekst zostawia sam napis „Potwierdź sprzedaż".
        order_id=_order_id(html or ""),
    )


def _content_lines(bodies: MailBodies | None, message: MailMessage) -> list[str]:
    """
    Niepuste linie treści maila - NAJPIERW z HTML-a, potem z części tekstowej.

    Kolejność jest tu odwrotna niż w `allegro_lokalnie.py` i wynika
    wprost z próbek: maile OLX są dwuczęściowe, ale część `text/plain`
    to sam szablon ogólny („Cześć! Dobra wiadomość - ktoś chce kupić
    Twój przedmiot z Przesyłką OLX", instrukcja pakowania paczki).
    Konkret - tytuł ogłoszenia i UUID transakcji - siedzi WYŁĄCZNIE
    w części HTML. Czytanie samego `text/plain` dawało zdarzenie
    poprawnie sklasyfikowane, ale bez tytułu i bez identyfikatora.

    Bierzemy obie części, bo część tekstowa bywa jedynym, co zostanie,
    gdy szablon HTML się zmieni - a doklejona na końcu niczego nie psuje.
    """
    parts: list[str] = []
    if bodies is not None:
        if bodies.html:
            parts.append(html_to_plain_text(bodies.html))
        if bodies.text:
            parts.append(bodies.text)
    if not parts:
        # Dociągnięcie treści z IMAP zawiodło - zostaje podgląd z bazy.
        parts.append(message.body_preview)

    lines: list[str] = []
    for part in parts:
        lines.extend(line.strip() for line in part.splitlines() if line.strip())
    return lines


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


def _listing_title(lines: list[str], event_type: str) -> str | None:
    """
    Tytuł ogłoszenia - inne miejsce w mailu sprzedażowym, inne w wiadomości.

    Szablony OLX podają go w jednym zdaniu razem z resztą tekstu
    („Twój przedmiot „X" został kupiony."), więc wyciągamy go wzorcem,
    a nie pozycją linii - kolejność akapitów zmienia się między
    kampaniami, brzmienie zdania nie.
    """
    if event_type == EVENT_NEW_ORDER:
        return _first_group(lines, _SALE_TITLE)
    if event_type == EVENT_NEW_MESSAGE:
        return _first_group(lines, _MESSAGE_TITLE)
    return None


def _first_group(lines: list[str], pattern: re.Pattern[str]) -> str | None:
    """Pierwsze dopasowanie wzorca w treści; `None`, gdy tytułu tam nie ma."""
    for line in lines:
        match = pattern.search(line)
        if match is not None:
            title = _collapse(match.group(1))
            if title:
                return title
    return None


def _order_id(haystack: str) -> str | None:
    """
    UUID transakcji z linku „Potwierdź sprzedaż".

    W mailach niesprzedażowych go nie ma - link do rozmowy prowadzi do
    `olx.pl/myaccount/answer/{uuid}` i to identyfikator WĄTKU, nie
    sprzedaży, więc świadomie go tu nie łapiemy.
    """
    match = _ORDER_LINK.search(haystack)
    return match.group(1).lower() if match else None


def _normalize(text: str) -> str:
    """Sprowadza tekst do postaci bez polskich znaków i wielkości liter."""
    folded = unicodedata.normalize("NFKD", text.lower().translate(_MANUAL_FOLD))
    return "".join(character for character in folded if not unicodedata.combining(character))


def _collapse(text: str) -> str:
    """Zwija białe znaki - temat maila bywa złamany na kilka linii przez serwer."""
    return " ".join(text.split())
