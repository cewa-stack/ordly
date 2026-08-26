"""
Testy rozpoznawania zdarzeń z powiadomień Allegro Lokalnie.

Każdy test poniżej działa na PRAWDZIWYM mailu z tej skrzynki
(`tests/fixtures/allegro_lokalnie/*.eml`), przepuszczonym przez tę samą
ścieżkę co produkcyjna: `_parse_message` z watchera IMAP -> `extract_bodies`
-> `parse_event`.

Dlaczego to ma znaczenie: pierwsza wersja tego parsera była zbudowana na
ZGADYWANYM brzmieniu szablonów i myliła się w połowie przypadków -
dopasowywała `"kup teraz"`, które okazało się generyczną etykietą typu
ogłoszenia obecną w KAŻDYM mailu, więc wiadomość od kupującego i doręczenie
paczki lądowały jako "nowe zamówienie". Testy na zmyślonych stringach tego
nie widziały, bo potwierdzały wyobrażenie o szablonie, a nie szablon.

Allegro Lokalnie nie ma API, więc te maile są JEDYNYM źródłem wiedzy
o tamtejszej sprzedaży - błąd tutaj znaczy przeoczone zamówienie.
"""

from __future__ import annotations

import pathlib
from decimal import Decimal
from email import message_from_bytes

import pytest

from app.domain.entities.allegro_lokalnie_event import (
    EVENT_INTEREST,
    EVENT_NEW_MESSAGE,
    EVENT_NEW_ORDER,
    EVENT_ORDER_STATUS,
    EVENT_UNKNOWN,
    AllegroLokalnieEvent,
)
from app.domain.entities.mail_message import MailMessage
from app.infrastructure.mail.allegro_lokalnie import parse_event
from app.infrastructure.mail.imap_watcher import _parse_message
from app.infrastructure.mail.mime import extract_bodies

FIXTURES = pathlib.Path(__file__).parents[2] / "fixtures" / "allegro_lokalnie"

SPRZEDANO_100 = (
    "Sprzedano 100szt. Butelka Gorilla 10ml Liquid Aromat Baza olejki DIY kosmetyki PET.eml"
)
SPRZEDANO_25 = (
    "Sprzedano 25szt. Butelka Gorilla 60ml Liquid Aromat Baza olejki DIY kosmetyki PET.eml"
)
SPRZEDANO_5 = (
    "Sprzedano 5szt. Butelka Gorilla 10ml Liquid Aromat Baza olejki DIY kosmetyki PET.eml"
)
SPRZEDANO_PLYTA = "Sprzedano Płyta gazowa AMICA PG0720 _ PMG2.0ZpZtR.eml"
WIADOMOSC_5 = "Nowa wiadomość do 5szt. Butelka Gorilla 10ml Liquid Aromat Baza olejki DIY kosmetyki PET.eml"
WIADOMOSC_PLYTA = "Nowa wiadomość do Płyta gazowa AMICA PG0720 _ PMG2.0ZpZtR.eml"
WARUNKI_DOSTAWY = (
    "Kupujący prosi o warunki dostawy 100szt. Butelka Gorilla 10ml Liquid Aromat "
    "Baza olejki DIY kosmetyki PET i innych przedmiotów.eml"
)
DORECZONO = (
    "Dostarczyliśmy Twoją paczkę z 25szt. Butelka Gorilla 60ml Liquid Aromat "
    "Baza olejki DIY kosmetyki PET.eml"
)

WSZYSTKIE = [
    SPRZEDANO_100,
    SPRZEDANO_25,
    SPRZEDANO_5,
    SPRZEDANO_PLYTA,
    WIADOMOSC_5,
    WIADOMOSC_PLYTA,
    WARUNKI_DOSTAWY,
    DORECZONO,
]


def wczytaj(nazwa: str) -> tuple[MailMessage, AllegroLokalnieEvent]:
    """Przepuszcza próbkę przez pełną ścieżkę produkcyjną."""
    raw = (FIXTURES / nazwa).read_bytes()
    message = _parse_message(raw)
    assert message is not None, f"{nazwa}: brak nagłówka Message-ID"
    bodies = extract_bodies(message_from_bytes(raw))
    return message, parse_event(message, bodies)


def zdarzenie(nazwa: str) -> AllegroLokalnieEvent:
    return wczytaj(nazwa)[1]


class TestKopertaISkrzynka:
    """Co widzi warstwa poczty, zanim w ogóle dojdzie do rozpoznawania zdarzeń."""

    @pytest.mark.parametrize("nazwa", WSZYSTKIE)
    def test_kazda_probka_jest_klasyfikowana_jako_allegro_lokalnie(self, nazwa: str):
        """
        Nadawca to `powiadomienia@allegrolokalnie.pl` - zawiera podciąg
        "allegro", więc bez sprawdzania "allegrolokalnie" NAJPIERW wszystkie
        te maile lądowałyby pod etykietą Allegro.pl.
        """
        message, _ = wczytaj(nazwa)

        assert message.source == "allegro_lokalnie"
        assert "allegrolokalnie.pl" in message.sender

    @pytest.mark.parametrize("nazwa", WSZYSTKIE)
    def test_podglad_nie_zawiera_surowego_html(self, nazwa: str):
        """
        Wszystkie te maile są JEDNOCZĘŚCIOWE `text/html` - nie mają części
        `text/plain`. Przed naprawą MIME podgląd zaczynałby się od
        `<!DOCTYPE HTML …`.
        """
        message, _ = wczytaj(nazwa)

        assert "<" not in message.body_preview
        assert "DOCTYPE" not in message.body_preview
        assert message.body_preview.strip() != ""

    def test_temat_nie_jest_zlamany_na_dwie_linie(self):
        """
        Regresja: serwer łamie długie nagłówki (RFC 5322 "folding"),
        więc po zdekodowaniu temat wyglądał tak: "Sprzedano 100szt.
        Butelka Gorilla 10ml Liquid Aromat Baza olejki\\n\\n DIY kosmetyki PET".
        """
        message, _ = wczytaj(SPRZEDANO_100)

        assert "\n" not in message.subject
        assert message.subject == (
            "Sprzedano 100szt. Butelka Gorilla 10ml Liquid Aromat Baza olejki "
            "DIY kosmetyki PET"
        )


class TestKlasyfikacja:
    """Typ zdarzenia rozstrzyga TEMAT - treść jest pełna napisów interfejsu."""

    @pytest.mark.parametrize(
        ("nazwa", "oczekiwany"),
        [
            (SPRZEDANO_100, EVENT_NEW_ORDER),
            (SPRZEDANO_25, EVENT_NEW_ORDER),
            (SPRZEDANO_5, EVENT_NEW_ORDER),
            (SPRZEDANO_PLYTA, EVENT_NEW_ORDER),
            (WIADOMOSC_5, EVENT_NEW_MESSAGE),
            (WIADOMOSC_PLYTA, EVENT_NEW_MESSAGE),
            (WARUNKI_DOSTAWY, EVENT_INTEREST),
            (DORECZONO, EVENT_ORDER_STATUS),
        ],
    )
    def test_rozpoznaje_typ_zdarzenia(self, nazwa: str, oczekiwany: str):
        assert zdarzenie(nazwa).event_type == oczekiwany

    def test_etykieta_kup_teraz_nie_robi_z_wiadomosci_zamowienia(self):
        """
        Sedno błędu pierwszej wersji: "kup teraz" to typ ogłoszenia,
        obecny w każdym mailu z Lokalnie - nie ma prawa decydować
        o klasyfikacji.
        """
        message, event = wczytaj(WIADOMOSC_PLYTA)

        assert "kup teraz" in message.body_preview.lower()
        assert event.event_type == EVENT_NEW_MESSAGE

    def test_tylko_sprzedaz_liczy_sie_jako_zamowienie(self):
        sprzedaz = [zdarzenie(n).is_order for n in (SPRZEDANO_100, DORECZONO)]
        rozmowa = [zdarzenie(n).is_order for n in (WIADOMOSC_5, WARUNKI_DOSTAWY)]

        assert sprzedaz == [True, True]
        assert rozmowa == [False, False]


class TestWyciaganeDane:
    """Pola, które trafiają do treści powiadomienia."""

    def test_sprzedaz_ma_tytul_ilosc_i_kwote_zaplacona(self):
        """
        `amount` to kwota, którą kupujący FAKTYCZNIE zapłacił (z dostawą),
        a nie cena jednostkowa ogłoszenia. Przy 4 sztukach po 71,98 zł
        różnica to 287,92 zł kontra 71,98 zł - powiadomienie z ceną
        jednostkową wprowadzałoby w błąd co do wartości sprzedaży.
        """
        event = zdarzenie(SPRZEDANO_100)

        assert event.listing_title == (
            "100szt. Butelka Gorilla 10ml Liquid Aromat Baza olejki DIY kosmetyki PET"
        )
        assert event.quantity == 4
        assert event.unit_amount == Decimal("71.98")
        assert event.amount == Decimal("287.92")

    def test_sprzedaz_z_dostawa_liczy_dostawe_do_kwoty(self):
        """5szt.: 9,99 zł za sztukę + 10,95 zł dostawy = 20,94 zł."""
        event = zdarzenie(SPRZEDANO_5)

        assert event.unit_amount == Decimal("9.99")
        assert event.amount == Decimal("20.94")

    def test_sprzedaz_ma_kupujacego(self):
        event = zdarzenie(SPRZEDANO_25)

        assert event.buyer == "ArchiTheOne (Artur Wisniewski)"

    def test_wiadomosc_ma_kupujacego_z_linii_zdarzenia(self):
        """
        Maile z wiadomością nie mają sekcji "Osoba kupująca", więc dane
        idą z linii zdarzenia: "Masz nową wiadomość od Piotr (DARROK)".

        UWAGA na kolejność: tam imię stoi PRZED loginem, a w sekcji
        "Osoba kupująca" odwrotnie (`Antek2034 (Antoni Ponieważ)`).
        Parser sprowadza oba warianty do tej samej postaci, żeby na
        liście zamówień kupujący nie zmieniał raz na raz miejsc.
        """
        event = zdarzenie(WIADOMOSC_PLYTA)

        assert event.buyer_login == "DARROK"
        assert event.buyer_name == "Piotr"
        assert event.buyer == "DARROK (Piotr)"

    def test_wiadomosc_ma_tytul_ogloszenia_i_cene_bez_kwoty_zaplaconej(self):
        """Nikt jeszcze nic nie kupił, więc "Łączna kwota zakupu" nie istnieje."""
        event = zdarzenie(WIADOMOSC_PLYTA)

        assert event.listing_title == "Płyta gazowa AMICA PG0720 / PMG2.0ZpZtR"
        assert event.unit_amount == Decimal("250.00")
        assert event.amount == Decimal("250.00")

    def test_doreczenie_paczki_ma_tytul_ogloszenia(self):
        event = zdarzenie(DORECZONO)

        assert event.listing_title == (
            "25szt. Butelka Gorilla 60ml Liquid Aromat Baza olejki DIY kosmetyki PET"
        )

    @pytest.mark.parametrize("nazwa", WSZYSTKIE)
    def test_kazda_probka_ma_tytul_ogloszenia_i_kwote(self, nazwa: str):
        """Bez tych dwóch pól powiadomienie nie powie ANI CZEGO, ANI ZA ILE."""
        event = zdarzenie(nazwa)

        assert event.listing_title, f"{nazwa}: brak tytułu ogłoszenia"
        assert event.amount is not None, f"{nazwa}: brak kwoty"

    @pytest.mark.parametrize("nazwa", WSZYSTKIE)
    def test_opis_nadaje_sie_do_tresci_powiadomienia(self, nazwa: str):
        event = zdarzenie(nazwa)

        assert event.opis
        assert "<" not in event.opis
        assert "\n" not in event.opis


class TestOdpornosc:
    """Nieznany szablon ma stracić etykietę, a nie zniknąć."""

    def _mail(self, subject: str, preview: str = "") -> MailMessage:
        message, _ = wczytaj(SPRZEDANO_25)
        return MailMessage(
            message_id=message.message_id,
            sender=message.sender,
            subject=subject,
            received_at=message.received_at,
            source=message.source,
            body_preview=preview,
        )

    def test_nieznany_temat_daje_unknown_ale_zachowuje_tresc(self):
        event = parse_event(self._mail("Coś zupełnie nowego", "Treść nie do rozpoznania"))

        assert event.event_type == EVENT_UNKNOWN
        assert event.subject == "Coś zupełnie nowego"
        assert event.snippet == "Treść nie do rozpoznania"

    def test_pusty_mail_nie_wywala_parsera(self):
        event = parse_event(self._mail("", ""))

        assert event.event_type == EVENT_UNKNOWN
        assert event.listing_title is None
        assert event.amount is None

    def test_dziala_na_samym_podgladzie_gdy_brak_pelnej_tresci(self):
        """
        Gdy dociągnięcie treści z IMAP zawiedzie, zdarzenie ma powstać
        z samego podglądu - uboższe, ale nie stracone.
        """
        message, _ = wczytaj(SPRZEDANO_25)

        event = parse_event(message)

        assert event.event_type == EVENT_NEW_ORDER
        assert event.listing_title == (
            "25szt. Butelka Gorilla 60ml Liquid Aromat Baza olejki DIY kosmetyki PET"
        )
