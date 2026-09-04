"""
Testy parsera poczty OLX na PRAWDZIWYCH mailach.

Komplet próbek leży w `tests/fixtures/olx/` i każda ma tu swój test -
ta sama zasada co przy Allegro Lokalnie, i z tego samego powodu:
pierwsza wersja tamtego modułu zgadywała brzmienie szablonów i myliła
się w połowie przypadków.

Osobna klasa `TestCzegoWMailuNieMa` pilnuje najważniejszego wniosku
z tych próbek: mail sprzedażowy z OLX nie zawiera kwoty. To on decyduje
o tym, że sprzedaż z OLX zostaje powiadomieniem, a nie zamówieniem -
gdyby OLX kiedyś zaczął podawać kwotę, te testy upadną i będzie to
sygnał, że decyzję można zmienić.
"""

from __future__ import annotations

import pathlib
from datetime import UTC, datetime
from email import message_from_bytes

import pytest

from app.domain.entities.mail_message import MailMessage
from app.domain.entities.olx_event import (
    EVENT_NEW_MESSAGE,
    EVENT_NEW_ORDER,
    EVENT_RETURN,
    EVENT_UNKNOWN,
    OlxEvent,
)
from app.infrastructure.mail.imap_watcher import _parse_message
from app.infrastructure.mail.mime import MailBodies, extract_bodies
from app.infrastructure.mail.olx import parse_event

FIXTURES = pathlib.Path(__file__).parents[2] / "fixtures" / "olx"

SPRZEDAZ_BUTELKI = "Kupujacy juz zaplacil, potwierdz sprzedaz do 15_29 16-12-2025.eml"
SPRZEDAZ_ZESTAW = "Kupujacy juz zaplacil, potwierdz sprzedaz do 14_07 14-11-2025.eml"
WIADOMOSC = "Wiadomosci dotyczace ogloszen.eml"
WIADOMOSC_2 = "Wiadomosci dotyczace ogloszen (1).eml"

WSZYSTKIE = [SPRZEDAZ_BUTELKI, SPRZEDAZ_ZESTAW, WIADOMOSC, WIADOMOSC_2]
SPRZEDAZE = [SPRZEDAZ_BUTELKI, SPRZEDAZ_ZESTAW]


def wczytaj(nazwa: str) -> tuple[MailMessage, OlxEvent]:
    """Przepuszcza próbkę przez pełną ścieżkę produkcyjną."""
    raw = (FIXTURES / nazwa).read_bytes()
    message = _parse_message(raw)
    assert message is not None, f"{nazwa}: brak nagłówka Message-ID"
    bodies = extract_bodies(message_from_bytes(raw))
    return message, parse_event(message, bodies)


def zdarzenie(nazwa: str) -> OlxEvent:
    return wczytaj(nazwa)[1]


class TestKopertaISkrzynka:
    """Co widzi warstwa poczty, zanim dojdzie do rozpoznawania zdarzeń."""

    @pytest.mark.parametrize("nazwa", WSZYSTKIE)
    def test_kazda_probka_jest_klasyfikowana_jako_olx(self, nazwa: str):
        message, _ = wczytaj(nazwa)

        assert message.source == "olx"
        assert "noreply@olx.pl" in message.sender

    @pytest.mark.parametrize("nazwa", WSZYSTKIE)
    def test_podglad_nie_zawiera_surowego_html(self, nazwa: str):
        message, _ = wczytaj(nazwa)

        assert "<" not in message.body_preview
        assert "DOCTYPE" not in message.body_preview

    def test_nadawca_nie_jest_marketingowy(self):
        """
        Prawdziwe powiadomienia idą z `noreply@olx.pl`, marketing
        z `powiadomienia@marketing.olx.pl` - filtr wykluczeń nie ma
        prawa odciąć tych pierwszych.
        """
        message, _ = wczytaj(SPRZEDAZ_BUTELKI)

        assert "marketing.olx.pl" not in message.sender


class TestKlasyfikacja:
    """Typ zdarzenia rozstrzyga TEMAT - treść jest pełna napisów interfejsu."""

    @pytest.mark.parametrize(
        ("nazwa", "oczekiwany"),
        [
            (SPRZEDAZ_BUTELKI, EVENT_NEW_ORDER),
            (SPRZEDAZ_ZESTAW, EVENT_NEW_ORDER),
            (WIADOMOSC, EVENT_NEW_MESSAGE),
            (WIADOMOSC_2, EVENT_NEW_MESSAGE),
        ],
    )
    def test_rozpoznaje_typ_zdarzenia(self, nazwa: str, oczekiwany: str):
        assert zdarzenie(nazwa).event_type == oczekiwany

    def test_emoji_w_temacie_nie_psuje_rozpoznania(self):
        """Temat sprzedażowy zaczyna się od 💵➡️👍 - normalizacja musi to przeżyć."""
        message, event = wczytaj(SPRZEDAZ_BUTELKI)

        assert message.subject.startswith("💵")
        assert event.event_type == EVENT_NEW_ORDER

    def test_napisy_o_sprzedazy_w_wiadomosci_nie_robia_z_niej_sprzedazy(self):
        """
        Odpowiednik błędu „kup teraz" z Allegro Lokalnie: mail
        z wiadomością ma w treści całą sekcję o Przesyłce OLX
        i sprzedających, a mimo to sprzedażą nie jest.
        """
        _, event = wczytaj(WIADOMOSC)

        assert event.event_type == EVENT_NEW_MESSAGE


class TestWyciaganeDane:
    """Pola, które trafiają do treści powiadomienia."""

    def test_sprzedaz_ma_tytul_ogloszenia(self):
        event = zdarzenie(SPRZEDAZ_BUTELKI)

        assert event.listing_title == (
            "5x Butelka Gorilla 60ml Każda Ilość | Na Liquid Aromat Klej Tusz | DIY"
        )

    def test_druga_sprzedaz_ma_swoj_tytul(self):
        """Tytuł z myślnikiem i ukośnikiem - wzorzec nie może się o nie potknąć."""
        event = zdarzenie(SPRZEDAZ_ZESTAW)

        assert (
            event.listing_title == "Zestaw buteleczek 10ml do kosmetyków / liquidów – 20 szt."
        )

    @pytest.mark.parametrize("nazwa", [WIADOMOSC, WIADOMOSC_2])
    def test_wiadomosc_ma_tytul_ogloszenia_ktorego_dotyczy(self, nazwa: str):
        """
        Temat maila z wiadomością jest ZAWSZE ten sam („Wiadomości
        dotyczące ogłoszeń"), więc bez tytułu ogłoszenia powiadomienia
        byłyby nie do odróżnienia od siebie.
        """
        event = zdarzenie(nazwa)

        assert event.listing_title == (
            "Butelki PET 10 ml do liquidów – zestaw 10 szt. + dozownik + zakrętka"
        )

    @pytest.mark.parametrize(
        ("nazwa", "uuid"),
        [
            (SPRZEDAZ_BUTELKI, "89e856ce-51a8-d273-4566-bc907f06ef2a"),
            (SPRZEDAZ_ZESTAW, "a04f4f11-4e3a-a7e4-ab79-a1e2e517473d"),
        ],
    )
    def test_sprzedaz_ma_numer_transakcji_z_linku(self, nazwa: str, uuid: str):
        """
        UUID siedzi WYŁĄCZNIE w adresie linku „Potwierdź sprzedaż",
        w części HTML - po nim odnajdziesz sprzedaż w panelu OLX.
        """
        assert zdarzenie(nazwa).order_id == uuid

    @pytest.mark.parametrize("nazwa", [WIADOMOSC, WIADOMOSC_2])
    def test_wiadomosc_nie_ma_numeru_transakcji(self, nazwa: str):
        """
        W mailu z wiadomością jest link do WĄTKU
        (`olx.pl/myaccount/answer/{uuid}`), a nie do sprzedaży - to inny
        identyfikator i świadomie go nie łapiemy.
        """
        assert zdarzenie(nazwa).order_id is None

    @pytest.mark.parametrize("nazwa", WSZYSTKIE)
    def test_opis_jest_tytulem_ogloszenia_a_nie_tematem(self, nazwa: str):
        event = zdarzenie(nazwa)

        assert event.opis == event.listing_title
        assert "Kupujący już zapłacił" not in event.opis

    @pytest.mark.parametrize("nazwa", WSZYSTKIE)
    def test_zaden_wyciagniety_tekst_nie_zawiera_html(self, nazwa: str):
        """Treść idzie na Telegram (HTML) i na push - surowe znaczniki wywróciłyby oba."""
        event = zdarzenie(nazwa)

        assert "<" not in event.opis
        assert "\n" not in event.opis


class TestCzegoWMailuNieMa:
    """
    Najważniejszy wniosek z tych próbek: mail z OLX nie podaje kwoty.

    To on decyduje, że sprzedaż z OLX zostaje powiadomieniem, a nie
    zamówieniem - zamówienie z kwotą 0 zł zafałszowałoby przychód,
    którego nie da się potem poprawić z aplikacji. Gdy te testy zaczną
    upadać, znaczy to, że OLX zmienił szablon i decyzję warto przemyśleć
    od nowa.
    """

    @pytest.mark.parametrize("nazwa", SPRZEDAZE)
    def test_w_mailu_sprzedazowym_nie_ma_zadnej_kwoty(self, nazwa: str):
        raw = (FIXTURES / nazwa).read_bytes()
        bodies = extract_bodies(message_from_bytes(raw))
        tresc = f"{bodies.text or ''}\n{bodies.html or ''}"

        assert "zł" not in tresc
        assert " PLN" not in tresc

    @pytest.mark.parametrize("nazwa", SPRZEDAZE)
    def test_encja_nie_ma_pola_na_kwote_ani_ilosc(self, nazwa: str):
        """
        Pól, których mail nie wypełnia, w encji po prostu nie ma -
        pusta `amount` czekająca na dane byłaby obietnicą bez pokrycia.
        """
        event = zdarzenie(nazwa)

        assert not hasattr(event, "amount")
        assert not hasattr(event, "quantity")
        assert not hasattr(event, "buyer_login")


class TestOdpornosc:
    """Job skrzynki chodzi w tle co 5 minut - parser nie może go zatrzymać."""

    @staticmethod
    def _mail(subject: str, preview: str = "") -> MailMessage:
        return MailMessage(
            message_id="<olx-x@olx.pl>",
            sender="OLX <noreply@olx.pl>",
            subject=subject,
            received_at=datetime(2026, 9, 4, 12, 0, tzinfo=UTC),
            source="olx",
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
        assert event.order_id is None

    def test_temat_zlamany_na_dwie_linie_jest_zwijany(self):
        """Serwer łamie długie nagłówki (RFC 5322 "folding")."""
        event = parse_event(self._mail("Wiadomości dotyczące\n  ogłoszeń"))

        assert event.subject == "Wiadomości dotyczące ogłoszeń"
        assert event.event_type == EVENT_NEW_MESSAGE

    def test_zwrot_rozpoznawany_po_temacie(self):
        """
        Nie mamy próbki zwrotu z OLX - ten test sprawdza REGUŁĘ, a nie
        to, że OLX tak tytułuje te maile. Gdy przyjdzie prawdziwy zwrot,
        dołóż go do `tests/fixtures/olx/` i dopisz test parametryzowany.
        """
        assert parse_event(self._mail("Zwrot przedmiotu")).event_type == EVENT_RETURN

    def test_dziala_na_samym_podgladzie_gdy_brak_pelnej_tresci(self):
        """
        Gdy dociągnięcie treści z IMAP zawiedzie, zdarzenie ma powstać
        z samego podglądu - uboższe (bez numeru transakcji, który siedzi
        w HTML-u), ale nie stracone.
        """
        message, _ = wczytaj(SPRZEDAZ_BUTELKI)

        event = parse_event(message)

        assert event.event_type == EVENT_NEW_ORDER
        assert event.order_id is None

    def test_tresc_z_html_a_gdy_brak_czesci_tekstowej(self):
        bodies = MailBodies(
            html="<html><body><p>Twój przedmiot „Butelka PET” został kupiony.</p></body></html>",
            text=None,
        )

        event = parse_event(self._mail("Potwierdź sprzedaż do 12:00"), bodies)

        assert event.listing_title == "Butelka PET"
