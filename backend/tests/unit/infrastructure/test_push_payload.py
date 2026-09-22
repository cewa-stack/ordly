"""
Testy katalogu powiadomień push - reguły z sekcji 03/04 koncepcji
`ordly-powiadomienia-push.html`.

To warstwa, której nie da się sprawdzić okiem: powiadomienie widać
dopiero na telefonie, w losowym momencie, i tylko raz. Dlatego reguły
("treść zawsze z liczbą", "akcje tylko do odczytu", "cisza 22:00-7:00")
są tu przypięte testami.
"""

from __future__ import annotations

import json
from datetime import datetime, time
from decimal import Decimal

import pytest

from app.infrastructure.webpush import push_payload


class TestQuietHours:
    """Okno ciszy 22:00-7:00 przechodzi przez północ."""

    @pytest.mark.parametrize(
        "moment",
        [time(22, 0), time(23, 30), time(0, 15), time(3, 0), time(6, 59)],
    )
    def test_godziny_nocne_sa_cisza(self, moment: time):
        assert push_payload.is_quiet_hour(moment) is True

    @pytest.mark.parametrize("moment", [time(7, 0), time(9, 41), time(15, 0), time(21, 59)])
    def test_godziny_dzienne_nie_sa_cisza(self, moment: time):
        assert push_payload.is_quiet_hour(moment) is False


class TestKatalogTresci:
    """Każde powiadomienie niesie konkretną liczbę (zasada z sekcji 04)."""

    def test_nowe_zamowienie_mowi_ile_czego_i_za_ile(self):
        """
        Powiadomienie ma wystarczyć do decyzji "otwieram czy nie".
        Kanał jest w treści, nie w tytule - tytuł z kanałem ucinał się
        na ekranie blokady.
        """
        payload = push_payload.new_order(
            marketplace="allegro",
            amount=Decimal("249.90"),
            currency="PLN",
            products=[(2, "Organizer na biurko")],
            external_id="abc12345-6789",
        )

        assert payload.title == "Nowe zamówienie"
        assert payload.body.startswith("Allegro · 2× Organizer na biurko — ")
        assert "Katarzyna" not in payload.body
        assert "249,90 zł" in payload.body
        assert payload.url == "/orders/abc12345-6789"
        assert payload.thread == "orders"

    def test_kwota_ma_nielamliwa_spacje_jako_separator_tysiecy(self):
        """
        Format 7.2: `2 340,00 zł`, nie `2,340.00 PLN`.

        Separator MUSI być niełamliwy (U+00A0) - tak samo jak w apce
        desktopowej i mobilnej, gdzie robi to `Intl.NumberFormat`.
        Zwykła spacja pozwoliłaby rozbić kwotę na dwie linijki.
        """
        payload = push_payload.new_order(
            marketplace="amazon",
            amount=Decimal("2340.00"),
            currency="PLN",
            products=[(1, "Lampka")],
            external_id="x",
        )

        assert "2 340,00 zł" in payload.body

    def test_zbiorcze_rozbija_na_kanaly_i_sumuje_kwoty(self):
        payload = push_payload.many_new_orders(
            count=4,
            per_channel={"allegro": 2, "amazon": 1, "ebay": 1},
            total_amount=Decimal("1218.40"),
            currency="PLN",
        )

        assert payload.title == "4 nowe zamówienia"
        assert "Allegro 2" in payload.body
        assert "1 218,40 zł" in payload.body

    def test_nowa_dyskusja_mowi_kto_o_co_i_do_kiedy(self):
        payload = push_payload.new_dispute(
            buyer_login="Kupiec99",
            reason="niezgodny z opisem",
            respond_by=datetime(2026, 7, 29, 8, 41),
            issue_id="81ecd951-ab12-4528-8154-af5699df2b1c",
        )

        assert payload.title == "Nowa dyskusja"
        assert payload.body == "Kupiec99: niezgodny z opisem — odpowiedz do 29.07, 08:41"
        assert payload.url == "/issues/81ecd951-ab12-4528-8154-af5699df2b1c"
        assert payload.thread == "issues"

    def test_nowa_dyskusja_pokazuje_godzine_a_nie_odliczanie(self):
        """
        Powiadomienie bywa czytane długo po dostarczeniu - „zostało
        6 godz." zdążyłoby się wtedy zestarzeć i skłamać. Konkretna
        godzina jest prawdziwa niezależnie od tego, kiedy się je otworzy.
        """
        payload = push_payload.new_dispute(
            buyer_login="Kupiec99",
            reason=None,
            respond_by=datetime(2026, 7, 29, 8, 41),
            issue_id="i-1",
        )

        assert "zostało" not in payload.body
        assert "29.07, 08:41" in payload.body

    def test_nowa_dyskusja_bez_terminu_go_nie_zmysla(self):
        """Gdy szablon maila nie podał terminu, treść po prostu go pomija."""
        payload = push_payload.new_dispute(
            buyer_login="Tomasz Lis", reason=None, respond_by=None, issue_id="i-1"
        )

        assert payload.body == "Tomasz Lis"

    def test_blad_synchronizacji_mowi_co_sie_stalo_i_kiedy_ponowi(self):
        """
        Ton z sekcji 7.3: co się stało i kiedy dalej. Bez przeprosin
        i bez zdania o innych kanałach - ORDLY ma jeden aktywny plugin,
        więc brzmiało zawsze tak samo i nic nie wnosiło.
        """
        payload = push_payload.sync_failed(channel="allegro", retry_in_minutes=5)

        assert payload.title == "Allegro nie odpowiada"
        assert payload.body == "Ponowna próba za 5 minut"
        assert "przepraszam" not in payload.body.lower()

    def test_odmowa_logowania_poczty_mowi_co_przepada_i_gdzie_szukac_powodu(self):
        """
        Ponawianie nie naprawi odrzuconego hasła, więc zamiast "ponowna
        próba" treść mówi, że sprzedaż z maili nie wpada, i kieruje na
        desktop - tylko tam widać dosłowny powód odmowy serwera.
        """
        payload = push_payload.mailbox_unavailable(login_rejected=True, retry_in_minutes=5)

        assert payload.title == "Poczta: odmowa logowania"
        assert "AllegroLokalnie i OLX" in payload.body
        assert "desktopie" in payload.body
        assert "Ponowna próba" not in payload.body
        assert payload.url == "/mailbox"
        assert payload.collapse_key == "sync:poczta"

    def test_brak_polaczenia_z_poczta_mowi_kiedy_ponowi(self):
        payload = push_payload.mailbox_unavailable(login_rejected=False, retry_in_minutes=5)

        assert payload.title == "Poczta nie odpowiada"
        assert payload.body.startswith("Ponowna próba za 5 minut")
        assert "AllegroLokalnie i OLX" in payload.body
        # Osobny klucz niż Allegro - alert poczty nie może nadpisać
        # na telefonie alertu o niedziałającym API zamówień.
        assert payload.collapse_key != push_payload.sync_failed(
            channel="allegro", retry_in_minutes=5
        ).collapse_key

    def test_potwierdzenie_hurtowni_jest_ciche_i_bez_akcji_wyciszenia(self):
        """Katalog oznacza tę pozycję jako „ciche" - nie budzi telefonu."""
        payload = push_payload.wholesaler_confirmed(
            wholesaler_name="Biurex", items_summary="30 szt. organizerów"
        )

        assert payload.silent is True
        assert [action["action"] for action in payload.actions] == ["open"]


class TestOdmianaPolska:
    """Liczebnik + rzeczownik - powiadomienia czyta się kilka razy dziennie."""

    @pytest.mark.parametrize(
        ("count", "expected"),
        [
            (1, "1 nowe zamówienie"),
            (2, "2 nowe zamówienia"),
            (5, "5 nowych zamówień"),
            (12, "12 nowych zamówień"),
            (22, "22 nowe zamówienia"),
        ],
    )
    def test_tytul_zbiorczego_odmienia_sie_poprawnie(self, count: int, expected: str):
        payload = push_payload.many_new_orders(
            count=count,
            per_channel={"allegro": count},
            total_amount=Decimal("100.00"),
            currency="PLN",
        )

        assert payload.title == expected


class TestSerializacja:
    """Kształt, który dostaje `sw.js` w aplikacji mobilnej."""

    def test_akcje_sa_wylacznie_do_odczytu(self):
        """
        Zasada z sekcji 04: żadnego „Przyjmij zwrot", „Oznacz jako
        spakowane" ani szybkiej odpowiedzi kupującemu.
        """
        payloads = [
            push_payload.new_order(
                marketplace="allegro",
                amount=Decimal("1.00"),
                currency="PLN",
                products=[(1, "Y")],
                external_id="z",
            ),
            push_payload.new_return(
                external_id="r-1", products_summary="Organizer", reason="rozmiar"
            ),
            push_payload.new_dispute(
                buyer_login="A", reason="b", respond_by=None, issue_id="i"
            ),
        ]

        for payload in payloads:
            actions = {action["action"] for action in payload.actions}
            assert actions <= {"open", "mute"}

    def test_json_niesie_tag_watek_url_i_akcje(self):
        payload = push_payload.new_return(
            external_id="A87990ff", products_summary="Organizer na biurko", reason="rozmiar"
        )

        data = json.loads(payload.to_json())

        assert data["thread"] == "returns"
        assert data["tag"] == "return:A87990ff"
        assert data["url"] == "/returns/A87990ff"
        assert data["title"] == "Nowy zwrot"

    def test_rozne_zwroty_nie_zastepuja_sie_nawzajem(self):
        """
        `tag` w Web Push ZASTĘPUJE poprzednie powiadomienie, więc dwa
        różne zdarzenia muszą mieć różne klucze - inaczej drugi zwrot
        skasowałby z ekranu blokady powiadomienie o pierwszym.
        """
        first = json.loads(
            push_payload.new_return(
                external_id="A87990ff", products_summary="A", reason="rozmiar"
            ).to_json()
        )
        second = json.loads(
            push_payload.new_return(
                external_id="B12345cc", products_summary="B", reason="rozmiar"
            ).to_json()
        )

        assert first["tag"] != second["tag"]

    def test_zbiorcze_zamowienia_zastepuja_poprzednie_zbiorcze(self):
        """
        Odwrotnie niż wyżej: „4 nowe zamówienia" ma ZASTĄPIĆ wcześniejsze
        „3 nowe zamówienia", a nie leżeć obok niego.
        """
        three = json.loads(
            push_payload.many_new_orders(
                count=3,
                per_channel={"allegro": 3},
                total_amount=Decimal("300.00"),
                currency="PLN",
            ).to_json()
        )
        four = json.loads(
            push_payload.many_new_orders(
                count=4,
                per_channel={"allegro": 4},
                total_amount=Decimal("400.00"),
                currency="PLN",
            ).to_json()
        )

        assert three["tag"] == four["tag"] == "orders"


class TestAllegroLokalnie:
    """
    Powiadomienie o zdarzeniu z Allegro Lokalnie - kanał bez API, więc
    push jest jedynym sygnałem, że coś się tam wydarzyło.
    """

    def test_nowe_zamowienie_z_kwota(self):
        payload = push_payload.allegro_lokalnie_event(
            event_type="new_order",
            listing_title="25szt. Butelka Gorilla 60ml Liquid Aromat",
            quantity=1,
            amount=Decimal("129.90"),
            message_id="<al-1@allegrolokalnie.pl>",
        )

        assert payload.title == "Nowe zamówienie"
        assert payload.body == (
            "AllegroLokalnie · 1× 25szt. Butelka Gorilla 60ml Liquid Aromat — 129,90 zł"
        )
        assert payload.thread == "mail"

    def test_ilosc_sztuk_trafia_do_tresci(self):
        """
        Przy 4 sztukach po 71,98 zł kwota zapłacona to 287,92 zł -
        powiadomienie musi pokazać OBIE liczby, inaczej nie wiadomo,
        czy 287,92 zł to cena, czy suma.
        """
        payload = push_payload.allegro_lokalnie_event(
            event_type="new_order",
            listing_title="100szt. Butelka Gorilla 10ml",
            quantity=4,
            amount=Decimal("287.92"),
            message_id="<al-8@allegrolokalnie.pl>",
        )

        assert "4× 100szt. Butelka Gorilla 10ml" in payload.body
        assert "287,92 zł" in payload.body

    def test_nazwa_kanalu_jest_w_tresci_i_bez_skrotu(self):
        """
        Tytuł z kanałem ("Nowe zamówienie · Allegro Lokalnie") ucinał się
        na ekranie blokady w połowie słowa, więc kanał przeniósł się do
        treści. Nazwa jest pełna - skrót w rodzaju "AL" wymagałby
        domyślania się, o który serwis chodzi.
        """
        payload = push_payload.allegro_lokalnie_event(
            event_type="new_order",
            listing_title="Butelki PET",
            quantity=None,
            amount=None,
            message_id="<al-9@allegrolokalnie.pl>",
        )

        assert "AllegroLokalnie" in payload.body
        assert "AL Lokalnie" not in payload.body
        assert len(payload.title) <= 24

    def test_zwrot_ma_wlasny_tytul_odrozny_od_zmiany_zamowienia(self):
        """
        Zwrot wymaga reakcji, „paczka dostarczona" i „anulowano" nie -
        a wszystkie trzy dostawały dotąd tytuł „Zmiana zamówienia".
        Na ekranie blokady widać wyłącznie tytuł, więc rozróżnienie
        musi być właśnie tam.
        """
        zwrot = push_payload.allegro_lokalnie_event(
            event_type="return",
            listing_title="Butelka Gorilla 60ml",
            quantity=1,
            amount=None,
            message_id="<al-zwrot@allegrolokalnie.pl>",
        )
        status = push_payload.allegro_lokalnie_event(
            event_type="order_status",
            listing_title="Butelka Gorilla 60ml",
            quantity=1,
            amount=None,
            message_id="<al-status@allegrolokalnie.pl>",
        )

        assert zwrot.title == "Zwrot / reklamacja"
        assert zwrot.title != status.title
        assert len(zwrot.title) <= 24

    def test_bez_kwoty_tresc_jej_nie_zmysla(self):
        payload = push_payload.allegro_lokalnie_event(
            event_type="new_message",
            listing_title="Płyta gazowa AMICA PG0720",
            quantity=None,
            amount=None,
            message_id="<al-2@allegrolokalnie.pl>",
        )

        assert "zł" not in payload.body
        assert payload.title == "Nowa wiadomość"

    def test_nierozpoznany_szablon_dostaje_neutralny_tytul(self):
        """
        Allegro może zmienić szablon maila bez ostrzeżenia. Lepiej
        powiadomić "coś przyszło" niż przemilczeć sprzedaż.
        """
        payload = push_payload.allegro_lokalnie_event(
            event_type="cos_nowego",
            listing_title="Nieznany temat",
            quantity=None,
            amount=None,
            message_id="<al-3@allegrolokalnie.pl>",
        )

        assert payload.title == "AllegroLokalnie"
        assert payload.body == "Nieznany temat"

    def test_tresc_nigdy_nie_zawiera_znacznikow_html(self):
        """
        Web Push nie renderuje HTML - `<b>` wyszłoby na ekran telefonu
        dosłownie. Treść z tematu maila od obcego nadawcy nie może
        wprowadzić znaczników do powiadomienia inną drogą niż katalog.
        """
        payload = push_payload.allegro_lokalnie_event(
            event_type="new_order",
            listing_title="Butelka Gorilla 10ml",
            quantity=1,
            amount=Decimal("10.00"),
            message_id="<al-4@allegrolokalnie.pl>",
        )

        assert "<" not in payload.title
        assert "<" not in payload.body

    def test_url_prowadzi_do_maila_z_zakodowanym_identyfikatorem(self):
        """
        Message-ID zawiera `<`, `>` i `@` - bez zakodowania rozjechałby
        ścieżkę powiadomienia i kliknięcie wylądowałoby na liście
        zamiast na wiadomości.
        """
        payload = push_payload.allegro_lokalnie_event(
            event_type="new_order",
            listing_title="Butelka Gorilla 10ml",
            quantity=None,
            amount=None,
            message_id="<al-5@allegrolokalnie.pl>",
        )

        assert payload.url == "/mailbox/%3Cal-5%40allegrolokalnie.pl%3E"
        assert "<" not in payload.url

    def test_kazde_zdarzenie_ma_wlasny_klucz_zastapienia(self):
        """
        Dwa różne zdarzenia mają zostać obok siebie na ekranie blokady,
        a nie zastąpić się nawzajem - stąd klucz per Message-ID.
        """
        first = push_payload.allegro_lokalnie_event(
            event_type="new_order",
            listing_title="A",
            quantity=None,
            amount=None,
            message_id="<a@allegrolokalnie.pl>",
        )
        second = push_payload.allegro_lokalnie_event(
            event_type="new_order",
            listing_title="B",
            quantity=None,
            amount=None,
            message_id="<b@allegrolokalnie.pl>",
        )

        assert json.loads(first.to_json())["tag"] != json.loads(second.to_json())["tag"]


class TestSiatkaBezpieczenstwa:
    """
    `strip_html` chroni kanał push przed treścią formatowaną pod Telegram.

    Zgłoszony błąd wyglądał na telefonie tak: „⚠️ <b>Sprzedaż poza
    magazynem</b> Zamówienie b2784ef0-…”. Telegram renderuje HTML,
    Web Push nie - a obie ścieżki schodziły się w jednym `send_text`.
    """

    def test_usuwa_znaczniki_telegramowe(self):
        tekst = push_payload.strip_html(
            "⚠️ <b>Sprzedaż poza magazynem</b>\nUżyj <code>/stock link</code>."
        )

        assert "<" not in tekst
        assert ">" not in tekst
        assert "Sprzedaż poza magazynem" in tekst
        assert "/stock link" in tekst

    def test_nie_rusza_zwyklego_tekstu(self):
        tekst = "Zamówienie na 129,90 zł czeka na spakowanie"

        assert push_payload.strip_html(tekst) == tekst


class TestTytulyMieszczaSieNaEkranieBlokady:
    """
    iOS ucina tytuł powiadomienia do JEDNEJ linii. Przy dymku 347 pt
    i zegarze po prawej mieści się około 24 znaków - dłuższy tytuł
    użytkownik czyta w połowie („Nowe zamówienie · Allegro Lok…”).
    """

    LIMIT = 24

    def test_wszystkie_tytuly_katalogu_sa_krotkie(self):
        payloads = [
            push_payload.new_order(
                marketplace="allegro_lokalnie",
                amount=Decimal("129.90"),
                currency="PLN",
                products=[(50, "Butelki PET 30 ml")],
                external_id="x",
            ),
            push_payload.new_dispute(
                buyer_login="a", reason="b", respond_by=None, issue_id="i"
            ),
            push_payload.new_return(external_id="r", products_summary="A", reason="b"),
            push_payload.morning_brief(
                pending_count=3, oldest_local=None, now_local=datetime(2026, 9, 22, 9, 0)
            ),
            push_payload.test_notification(),
            push_payload.sync_failed(channel="allegro", retry_in_minutes=5),
            push_payload.mailbox_unavailable(login_rejected=True, retry_in_minutes=5),
            push_payload.mailbox_unavailable(login_rejected=False, retry_in_minutes=5),
            push_payload.allegro_lokalnie_event(
                event_type="new_order",
                listing_title="A",
                quantity=None,
                amount=None,
                message_id="<m@x>",
            ),
            push_payload.olx_event(event_type="new_order", opis="A", message_id="<m@olx.pl>"),
            push_payload.olx_event(event_type="return", opis="A", message_id="<m@olx.pl>"),
            push_payload.olx_event(
                event_type="new_message", opis="A", message_id="<m@olx.pl>"
            ),
        ]

        zbyt_dlugie = [p.title for p in payloads if len(p.title) > self.LIMIT]
        assert zbyt_dlugie == []


class TestOlx:
    """
    Kanał, o którym ORDLY dowiaduje się wyłącznie z poczty.

    Sprzedaż z OLX NIE staje się zamówieniem - mail nie podaje kwoty
    (patrz `domain/entities/olx_event.py`), więc zostaje powiadomieniem.
    """

    @staticmethod
    def _payload(event_type: str, opis: str = "Butelki PET 10 ml do liquidów"):
        return push_payload.olx_event(
            event_type=event_type, opis=opis, message_id="<olx-1@olx.pl>"
        )

    def test_nazwa_kanalu_zostaje_w_tytule(self):
        """
        Odwrotnie niż przy Allegro Lokalnie: „OLX" to trzy znaki, więc nic
        się nie ucina, a bez nich „Nowa wiadomość" z OLX byłaby na ekranie
        blokady nie do odróżnienia od tej z Lokalnie.
        """
        payload = self._payload("new_message")

        assert payload.title == "Nowa wiadomość · OLX"
        assert len(payload.title) <= 24

    def test_sprzedaz_mowi_czego_dotyczy(self):
        """Tytuł niesie kanał, treść - pozycję, której sprzedaż dotyczy."""
        payload = self._payload("new_order")

        assert payload.title == "Sprzedano · OLX"
        assert "Butelki PET" in payload.body

    def test_sprzedaz_nie_udaje_nowego_zamowienia(self):
        """„Nowe zamówienie" znaczy w ORDLY, że rekord powstał. Tu nie powstaje."""
        assert "zamówienie" not in self._payload("new_order").title.lower()

    def test_zwrot_i_wiadomosc_maja_rozne_tytuly(self):
        zwrot = self._payload("return")
        wiadomosc = self._payload("new_message")

        assert zwrot.title == "Zwrot / reklamacja · OLX"
        assert zwrot.title != wiadomosc.title

    def test_nierozpoznany_szablon_dostaje_neutralny_tytul(self):
        """Lepiej powiadomić „coś przyszło" niż przemilczeć sprzedaż."""
        payload = self._payload("unknown", opis="Coś nowego z OLX")

        assert payload.title == "OLX"
        assert "Coś nowego z OLX" in payload.body

    def test_nazwa_kanalu_nie_powtarza_sie_w_tresci(self):
        assert self._payload("new_message").body.count("OLX") == 0

    def test_tresc_nie_zmysla_kwoty(self):
        """Maila z OLX nie da się zapytać o cenę - w treści jej po prostu nie ma."""
        for typ in ("new_order", "new_message", "return", "unknown"):
            assert "zł" not in self._payload(typ).body

    def test_klikniecie_prowadzi_do_maila(self):
        payload = push_payload.olx_event(
            event_type="unknown", opis="A", message_id="<olx-6@olx.pl>"
        )

        assert payload.url.startswith("/mailbox/")
        assert payload.collapse_key == "olx:<olx-6@olx.pl>"


# ----------------------------------------------------------------------
# Propozycje "Nokturn" (2026-09-22) - buildery czekajace na akceptacje
# podgladu. Testujemy je juz teraz, bo podglad jest z nich generowany.
# ----------------------------------------------------------------------


class TestOrderCancelled:
    def test_jest_ciche_i_bez_loginu_kupujacego(self):
        payload = push_payload.order_cancelled(
            marketplace="allegro",
            amount=Decimal("60.94"),
            currency="PLN",
            products=[(2, "Butelki PET 30 ml")],
            external_id="A-1",
        )

        assert payload.silent is True
        assert payload.title == "Zamówienie anulowane"
        assert "Allegro" in payload.body
        assert "60,94" in payload.body
        assert len(payload.title) <= 24


class TestSinceLabel:
    def test_dzisiaj(self):
        assert (
            push_payload.since_label(datetime(2026, 9, 22, 7, 12), datetime(2026, 9, 22, 9, 0))
            == "dziś 7:12"
        )

    def test_wczoraj(self):
        assert (
            push_payload.since_label(datetime(2026, 9, 21, 17, 40), datetime(2026, 9, 22, 9, 0))
            == "wczoraj 17:40"
        )

    def test_starsze_w_dniach(self):
        assert (
            push_payload.since_label(datetime(2026, 9, 18, 10, 0), datetime(2026, 9, 22, 9, 0))
            == "4 dni"
        )


class TestMorningBrief:
    NOW = datetime(2026, 9, 22, 9, 0)

    def test_nic_nie_czeka_nic_nie_wychodzi(self):
        assert (
            push_payload.morning_brief(pending_count=0, oldest_local=None, now_local=self.NOW)
            is None
        )

    def test_tytul_niesie_najpilniejsze_a_tresc_reszte(self):
        payload = push_payload.morning_brief(
            pending_count=3,
            oldest_local=datetime(2026, 9, 21, 17, 40),
            now_local=self.NOW,
            open_issues=2,
            open_returns=1,
        )

        assert payload is not None
        assert payload.title == "3 do spakowania"
        assert payload.body == "Najstarsze od wczoraj 17:40 · 2 dyskusje · 1 zwrot"
        # Od redesignu Start pokazuje dokladnie te trzy liczby.
        assert payload.url == "/start"

    def test_bez_zamowien_tytul_mowi_o_dyskusjach(self):
        payload = push_payload.morning_brief(
            pending_count=0, oldest_local=None, now_local=self.NOW, open_issues=5
        )

        assert payload is not None
        assert payload.title == "5 dyskusji czeka"

    def test_tytul_miesci_sie_na_ekranie_blokady(self):
        payload = push_payload.morning_brief(
            pending_count=0, oldest_local=None, now_local=self.NOW, open_issues=22
        )

        assert payload is not None
        assert len(payload.title) <= 24


class TestAttentionBadge:
    def test_suma_wymaga_uwagi_z_ekranu_start(self):
        assert push_payload.attention_badge(pending=3, open_issues=2, open_returns=1) == 6


class TestTestNotification:
    def test_tytul_mowi_co_sprawdzasz_i_miesci_sie(self):
        payload = push_payload.test_notification()

        assert payload.title == "Powiadomienia działają"
        assert len(payload.title) <= 24
        # "from ORDLY" dokłada Safari - treść nie musi powtarzać nazwy.
        assert "ORDLY" not in payload.body
