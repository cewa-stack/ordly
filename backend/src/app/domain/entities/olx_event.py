"""
Encja domenowa zdarzenia z OLX (kanał bez API, tylko powiadomienia e-mail).

Bliźniacza wobec `allegro_lokalnie_event.py` i celowo osobna: OLX to inny
serwis, z innym szablonem maila, a sklejenie obu pod jedną encją
oznaczałoby, że każda zmiana szablonu po jednej stronie rusza kod
obsługujący drugą.

RÓŻNICA WOBEC ALLEGRO LOKALNIE, KTÓRA TŁUMACZY KSZTAŁT TEJ KLASY.
Sprzedaż z Allegro Lokalnie staje się pełnoprawnym zamówieniem ORDLY,
bo mail podaje komplet: ilość, cenę jednostkową, kwotę zapłaconą
i kupującego. **Mail sprzedażowy z OLX nie podaje żadnej kwoty** - ani
ceny ogłoszenia, ani sumy zapłaconej; mówi wyłącznie „Płatność została
dokonana" (sprawdzone na próbkach w `tests/fixtures/olx/`, w części
tekstowej i w HTML-u). Nie podaje też kupującego.

Zamówienie zbudowane z takiego maila musiałoby wejść do statystyk
z kwotą 0 zł albo ze zmyśloną - a przychodu nie da się potem poprawić
z aplikacji. Dlatego sprzedaż z OLX zostaje POWIADOMIENIEM: mówi, co
i kiedy się sprzedało, ale nie rusza magazynu ani statystyk. Stan
odejmujesz sam, wiedząc dokładnie, czego dotyczy.

Stąd ta encja ma tylko pola, które w mailu FAKTYCZNIE są. Gdyby OLX
kiedyś zaczął podawać kwotę, doszłyby tu pola `quantity`/`amount`,
serwis tworzący zamówienia (wzór: `allegro_lokalnie_orders_service.py`)
i gałąź w `handle_olx_event` - ale dopóki maila z kwotą nie widzieliśmy,
takiego kodu tu nie ma.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

#: Typy zdarzeń rozpoznawane w powiadomieniach OLX. Nazwy odpowiadają
#: temu, co realnie wysyła serwis - patrz próbki w `tests/fixtures/olx/`.
EVENT_NEW_ORDER = "new_order"
EVENT_NEW_MESSAGE = "new_message"
EVENT_RETURN = "return"
EVENT_UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class OlxEvent:
    """
    Zdarzenie z OLX odczytane z jednego powiadomienia e-mail.

    `message_id` (nagłówek `Message-ID` maila) jest naturalnym kluczem
    zdarzenia - ten sam mail nigdy nie wygeneruje dwóch powiadomień,
    bo jest też kluczem głównym tabeli `mail_messages`.

    Pola opisowe są `None`, gdy szablon maila ich nie zawierał albo gdy
    parser ich nie rozpoznał. Nigdy nie są zgadywane - brak danych to
    brak danych.
    """

    message_id: str
    event_type: str
    subject: str
    snippet: str
    received_at: datetime
    #: Tytuł ogłoszenia, np. „5x Butelka Gorilla 60ml Każda Ilość…”.
    #: W mailu sprzedażowym stoi w zdaniu „Twój przedmiot „…” został
    #: kupiony”, w mailu z wiadomością - po „…do ogłoszenia:”.
    listing_title: str | None = None
    #: UUID transakcji z linku „Potwierdź sprzedaż”
    #: (`delivery.olx.pl/orders/sales/{uuid}`). Jedyny stabilny numer,
    #: jaki OLX podaje w mailu - po nim odnajdziesz sprzedaż w panelu
    #: serwisu. Jest wyłącznie w mailach sprzedażowych.
    order_id: str | None = None

    @property
    def opis(self) -> str:
        """
        Najkrótszy sensowny opis zdarzenia do treści powiadomienia.

        Tytuł ogłoszenia jest lepszy od tematu maila, bo temat OLX-a jest
        dla wszystkich wiadomości IDENTYCZNY („Wiadomości dotyczące
        ogłoszeń”), a przy sprzedaży to głównie termin potwierdzenia.
        """
        return self.listing_title or self.subject or self.snippet
