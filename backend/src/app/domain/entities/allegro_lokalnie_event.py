"""Encja domenowa zdarzenia z Allegro Lokalnie (kanał bez API, tylko powiadomienia e-mail)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

#: Typy zdarzeń rozpoznawane w powiadomieniach Allegro Lokalnie.
#: Nazwy odpowiadają temu, co realnie wysyła serwis - patrz próbki
#: w `tests/fixtures/allegro_lokalnie/`.
EVENT_NEW_ORDER = "new_order"
EVENT_NEW_MESSAGE = "new_message"
EVENT_INTEREST = "interest"
EVENT_ORDER_STATUS = "order_status"
EVENT_UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class AllegroLokalnieEvent:
    """
    Zdarzenie z Allegro Lokalnie odczytane z jednego powiadomienia e-mail.

    Świadomie NIE jest `Order`: z maila nie da się odtworzyć powiązań
    magazynowych ani statusu realizacji, a udawanie zamówienia wpuściłoby
    dane odczytane z szablonu maila w stany magazynowe i statystyki
    sprzedaży. To informacja o czymś, co wydarzyło się w serwisie, którym
    z ORDLY i tak nie da się sterować - Allegro Lokalnie nie ma
    publicznego API, więc zakres jest z natury "tylko do odczytu".

    `message_id` (nagłówek `Message-ID` maila) jest naturalnym kluczem
    zdarzenia - ten sam mail nigdy nie wygeneruje dwóch powiadomień,
    bo jest też kluczem głównym tabeli `mail_messages`.

    Pola opisowe są `None`, gdy szablon maila ich nie zawierał albo gdy
    parser ich nie rozpoznał. Nigdy nie są zgadywane - brak danych to
    brak danych, bo zmyślona kwota w powiadomieniu jest gorsza niż jej
    nieobecność.
    """

    message_id: str
    event_type: str
    subject: str
    snippet: str
    received_at: datetime
    #: Tytuł ogłoszenia, np. "25szt. Butelka Gorilla 60ml Liquid Aromat…".
    listing_title: str | None = None
    #: Login kupującego, np. "Antek2034".
    buyer_login: str | None = None
    #: Imię i nazwisko kupującego, np. "Antoni Ponieważ".
    buyer_name: str | None = None
    #: Liczba sprzedanych sztuk ogłoszenia.
    quantity: int | None = None
    #: Cena jednostkowa ogłoszenia.
    unit_amount: Decimal | None = None
    #: Kwota, którą kupujący faktycznie zapłacił (z dostawą). Przy
    #: zdarzeniach niesprzedażowych zostaje ceną jednostkową ogłoszenia.
    amount: Decimal | None = None
    #: Identyfikator transakcji z linku "Zobacz szczegóły" w mailu
    #: (`/konto/oferty/transakcja/{uuid}`). Jedyny stabilny numer, jaki
    #: Allegro Lokalnie w ogóle podaje - jest wyłącznie w mailach
    #: sprzedażowych i to on staje się numerem zamówienia w ORDLY.
    transaction_id: str | None = None

    @property
    def is_order(self) -> bool:
        """Czy zdarzenie dotyczy sprzedaży (a nie rozmowy z kupującym)."""
        return self.event_type in (EVENT_NEW_ORDER, EVENT_ORDER_STATUS)

    @property
    def buyer(self) -> str | None:
        """
        Kupujący do treści powiadomienia: `login (Imię Nazwisko)`.

        Allegro Lokalnie podaje raz jedno, raz drugie, a raz oba - stąd
        złożenie z tego, co akurat jest.
        """
        if self.buyer_login and self.buyer_name:
            return f"{self.buyer_login} ({self.buyer_name})"
        return self.buyer_login or self.buyer_name

    @property
    def can_become_order(self) -> bool:
        """
        Czy z tego zdarzenia da się zbudować pełne zamówienie w ORDLY.

        Wymagamy kompletu, bo zamówienie zdejmuje stany magazynowe i
        wchodzi do statystyk sprzedaży - rekord zbudowany na połowie
        danych zafałszowałby jedno i drugie. Braki nie są uzupełniane
        wartościami domyślnymi; niepełne zdarzenie zostaje zwykłym
        powiadomieniem ze skrzynki.
        """
        return (
            self.event_type == EVENT_NEW_ORDER
            and self.transaction_id is not None
            and self.listing_title is not None
            and self.quantity is not None
            and self.unit_amount is not None
            and self.amount is not None
        )

    @property
    def opis(self) -> str:
        """
        Najkrótszy sensowny opis zdarzenia do treści powiadomienia.

        Tytuł ogłoszenia jest lepszy od tematu maila, bo temat powiela
        prefiks („Sprzedano …”), który i tak siedzi już w tytule
        powiadomienia.
        """
        return self.listing_title or self.subject or self.snippet
