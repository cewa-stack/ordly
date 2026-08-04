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
from datetime import time
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

    def test_nowe_zamowienie_ma_kanal_kupujacego_i_kwote(self):
        payload = push_payload.new_order(
            marketplace="allegro",
            buyer_login="Katarzyna Wójcik",
            amount=Decimal("249.90"),
            currency="PLN",
            products_summary="Organizer na biurko x2",
            external_id="abc12345-6789",
        )

        assert payload.title == "Nowe zamówienie · Allegro"
        assert "Katarzyna Wójcik" in payload.body
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
            buyer_login="Jan",
            amount=Decimal("2340.00"),
            currency="PLN",
            products_summary="Lampka x1",
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
        assert "Allegro (2)" in payload.body
        assert "1 218,40 zł" in payload.body

    def test_niski_stan_mowi_ile_zostalo_przy_jakim_progu(self):
        payload = push_payload.low_stock(
            name="Etui na kable", sku="ETU-014", stock=3, min_stock=20
        )

        assert payload.title == "Niski stan"
        assert "zostały 3 szt." in payload.body
        assert "progu 20" in payload.body
        assert payload.url == "/stock/ETU-014"

    def test_pytanie_bez_czasu_do_limitu_nie_zmysla_liczby_godzin(self):
        """Gdy nie znamy limitu kanału, treść po prostu go pomija."""
        payload = push_payload.unanswered_question(
            buyer_login="Tomasz Lis",
            subject="termin wysyłki",
            hours_left=None,
            issue_id="i-1",
        )

        assert "Zostało" not in payload.body
        assert "Tomasz Lis" in payload.body

    def test_blad_synchronizacji_mowi_co_zadzialalo_i_kiedy_ponowi(self):
        """Ton z sekcji 7.3: co się stało, co mimo to zadziałało, kiedy dalej."""
        payload = push_payload.sync_failed(
            channel="allegro", healthy_channels=3, retry_in_minutes=5
        )

        assert payload.title == "Allegro nie odpowiedziało"
        assert "Pozostałe 3 kanały zaktualizowane" in payload.body
        assert "za 5 minut" in payload.body
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
        [(1, "1 nowe zamówienie"), (2, "2 nowe zamówienia"), (5, "5 nowych zamówień"),
         (12, "12 nowych zamówień"), (22, "22 nowe zamówienia")],
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
                buyer_login="X",
                amount=Decimal("1.00"),
                currency="PLN",
                products_summary="Y",
                external_id="z",
            ),
            push_payload.new_return(
                external_id="r-1", products_summary="Organizer", reason="rozmiar"
            ),
            push_payload.unanswered_question(
                buyer_login="A", subject="B", hours_left=22, issue_id="i"
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
        assert data["title"] == "Nowy zwrot do decyzji"

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
