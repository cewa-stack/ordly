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

    def test_niski_stan_mowi_ile_zostalo_przy_jakim_progu(self):
        payload = push_payload.low_stock(
            name="Etui na kable", sku="ETU-014", stock=3, min_stock=20
        )

        assert payload.title == "Niski stan"
        assert payload.body == "Etui na kable — 3 szt. (próg 20)"
        assert payload.url == "/stock/ETU-014"

    def test_nowa_dyskusja_mowi_kto_o_co_i_do_kiedy(self):
        payload = push_payload.new_dispute(
            buyer_login="Rexpiot",
            reason="niezgodny z opisem",
            respond_by=datetime(2026, 7, 29, 8, 41),
            issue_id="81ecd951-ab12-4528-8154-af5699df2b1c",
        )

        assert payload.title == "Nowa dyskusja"
        assert payload.body == "Rexpiot: niezgodny z opisem — odpowiedz do 29.07, 08:41"
        assert payload.url == "/issues/81ecd951-ab12-4528-8154-af5699df2b1c"
        assert payload.thread == "issues"

    def test_nowa_dyskusja_pokazuje_godzine_a_nie_odliczanie(self):
        """
        Powiadomienie bywa czytane długo po dostarczeniu - „zostało
        6 godz." zdążyłoby się wtedy zestarzeć i skłamać. Konkretna
        godzina jest prawdziwa niezależnie od tego, kiedy się je otworzy.
        """
        payload = push_payload.new_dispute(
            buyer_login="Rexpiot",
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

    def test_rozne_niskie_stany_nie_zastepuja_sie_nawzajem(self):
        """
        `tag` w Web Push ZASTĘPUJE poprzednie powiadomienie, więc dwa
        różne produkty muszą mieć różne klucze - inaczej ostrzeżenie
        o drugim SKU skasowałoby to o pierwszym.
        """
        first = json.loads(
            push_payload.low_stock(name="A", sku="PET30", stock=1, min_stock=10).to_json()
        )
        second = json.loads(
            push_payload.low_stock(name="B", sku="KRO60", stock=2, min_stock=10).to_json()
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


class TestSprzedazPozaMagazynem:
    """Nowa pozycja katalogu - zdarzenie, które wywołało całe zgłoszenie."""

    def test_tytul_mowi_co_sie_stalo_a_tresc_ktorej_pozycji_dotyczy(self):
        payload = push_payload.unmatched_products(
            reference="b2784ef0-a0c0-11f1-ae34-979fa0b8ac2d",
            product_names=[
                "Butelki PET 30 ml z zakrętką",
                "Nakrętki DIN18 czarne",
                "Kroplomierze LDPE",
            ],
        )

        assert payload.title == "Sprzedaż poza magazynem"
        assert payload.body == "Butelki PET 30 ml z zakrętką +2 poz. — stan bez zmian"

    def test_prowadzi_do_zamowienia_a_nie_do_ustawien(self):
        """
        Poprzednio szło to przez `send_text`, który zawsze otwiera
        `/settings` - czyli ekran niezwiązany ze zdarzeniem.
        """
        payload = push_payload.unmatched_products(
            reference="b2784ef0-a0c0", product_names=["Butelki PET"]
        )

        assert payload.url == "/orders/b2784ef0-a0c0"
        assert payload.thread == "stock"

    def test_jedna_pozycja_nie_dostaje_licznika(self):
        payload = push_payload.unmatched_products(
            reference="x", product_names=["Butelki PET 30 ml"]
        )

        assert payload.body == "Butelki PET 30 ml — stan bez zmian"

    def test_brak_pozycji_nie_wywala_buildera(self):
        payload = push_payload.unmatched_products(reference="x", product_names=[])

        assert "brak danych" in payload.body

    def test_tresc_nie_zawiera_znacznikow_html(self):
        """Sedno zgłoszenia: na ekranie blokady nie ma prawa być `<b>`."""
        payload = push_payload.unmatched_products(
            reference="b2784ef0", product_names=["Butelki PET 30 ml"]
        )

        assert "<" not in payload.title
        assert "<" not in payload.body


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
            push_payload.low_stock(name="A", sku="S", stock=1, min_stock=10),
            push_payload.new_dispute(
                buyer_login="a", reason="b", respond_by=None, issue_id="i"
            ),
            push_payload.new_return(external_id="r", products_summary="A", reason="b"),
            push_payload.pending_packing(count=3, oldest_since="wczoraj"),
            push_payload.sync_failed(channel="allegro", retry_in_minutes=5),
            push_payload.unmatched_products(reference="r", product_names=["A"]),
            push_payload.allegro_lokalnie_event(
                event_type="new_order",
                listing_title="A",
                quantity=None,
                amount=None,
                message_id="<m@x>",
            ),
        ]

        zbyt_dlugie = [p.title for p in payloads if len(p.title) > self.LIMIT]
        assert zbyt_dlugie == []
