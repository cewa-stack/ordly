"""
Testy kalkulacji ceny Ordlaka (`bot_ordlak/bot.md`, sekcja 5).

Kalkulacja jest deterministyczna i celowo NIE przechodzi przez AI, więc
da się ją przetestować dokładnie - to jest ta część modułu, która musi
się zgadzać co do grosza.
"""

from __future__ import annotations

import pytest

from app.services.ordlak_service import OrdlakError, calculate_price


class TestCalculatePrice:
    def test_przyklad_z_dokumentacji(self):
        """Zakup 25, sprowadzenie 8, wysyłka 12, prowizja 10%, marża 30% → 57,00 zł."""
        breakdown = calculate_price(
            purchase_cost=25.0,
            inbound_shipping_cost=8.0,
            buyer_shipping_cost=12.0,
            commission_percent=10.0,
            target_margin_percent=30.0,
        )

        assert breakdown.suggested_price == 57.0
        assert breakdown.commission_amount == 6.9

    def test_prowizja_liczona_od_ceny_plus_wysylki(self):
        """
        Kluczowa zasada Allegro: prowizja idzie od ceny I kosztu wysyłki
        pobranego od kupującego. Gdyby liczyła się od samej ceny, przy
        wysyłce 12 zł i stawce 10% wyszłoby 5,70 zamiast 6,90.
        """
        breakdown = calculate_price(25.0, 8.0, 12.0, 10.0, 30.0)

        od_samej_ceny = round(0.10 * breakdown.suggested_price, 2)
        assert breakdown.commission_amount != od_samej_ceny
        assert breakdown.commission_amount == pytest.approx(
            0.10 * (breakdown.suggested_price + 12.0), abs=0.01
        )

    def test_marza_docelowa_faktycznie_wychodzi(self):
        """Cena musi spełniać równanie, z którego została wyprowadzona."""
        breakdown = calculate_price(25.0, 8.0, 12.0, 10.0, 30.0)
        cena = breakdown.suggested_price

        zysk = cena - breakdown.commission_amount - 25.0 - 8.0

        assert zysk == pytest.approx(0.30 * cena, abs=0.01)

    def test_darmowa_wysylka_nie_podbija_prowizji(self):
        """Przy wysyłce 0 zł prowizja liczy się od samej ceny."""
        breakdown = calculate_price(100.0, 0.0, 0.0, 10.0, 20.0)

        assert breakdown.suggested_price == pytest.approx(142.86, abs=0.01)
        assert breakdown.commission_amount == pytest.approx(
            0.10 * breakdown.suggested_price, abs=0.01
        )

    def test_prowizja_i_marza_100_procent_daje_czytelny_blad(self):
        with pytest.raises(OrdlakError, match="mniejsze niż 100%"):
            calculate_price(25.0, 8.0, 12.0, 60.0, 40.0)

    def test_prowizja_i_marza_powyzej_100_procent_daje_czytelny_blad(self):
        with pytest.raises(OrdlakError, match="mniejsze niż 100%"):
            calculate_price(25.0, 8.0, 12.0, 70.0, 50.0)

    def test_ujemny_koszt_odrzucony(self):
        with pytest.raises(OrdlakError, match="nie może być ujemna"):
            calculate_price(-1.0, 0.0, 0.0, 10.0, 30.0)

    def test_zerowe_koszty_daja_zerowa_cene(self):
        """Brzegowy przypadek: nic nie kosztuje, więc nie ma z czego liczyć marży."""
        breakdown = calculate_price(0.0, 0.0, 0.0, 10.0, 30.0)

        assert breakdown.suggested_price == 0.0
        assert breakdown.commission_amount == 0.0

    def test_zwraca_wszystkie_dane_wejsciowe(self):
        """UI renderuje kartę ceny z tego jednego obiektu - musi mieć komplet."""
        breakdown = calculate_price(25.0, 8.0, 12.0, 10.0, 30.0)

        assert breakdown.purchase_cost == 25.0
        assert breakdown.inbound_shipping_cost == 8.0
        assert breakdown.buyer_shipping_cost == 12.0
        assert breakdown.commission_percent == 10.0
        assert breakdown.target_margin_percent == 30.0
