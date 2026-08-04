"""
Testy progu zbiorczego powiadomień: 3 zamówienia w 15 minut (sekcja 04).

Sens tej reguły widać dopiero na skrajnym przypadku: nocna
synchronizacja wciąga kilkanaście zamówień naraz i bez progu telefon
dostaje kilkanaście osobnych wibracji pod rząd.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from app.infrastructure.webpush.order_batcher import OrderPushBatcher
from app.utils.time import utc_now


class TestOrderPushBatcher:
    """Zachowanie okna 15-minutowego."""

    def test_pierwsze_dwa_zamowienia_ida_osobno(self, sample_order):
        batcher = OrderPushBatcher()
        now = utc_now()

        first = batcher.accept(sample_order, now=now)
        second = batcher.accept(
            replace(sample_order, external_id="ORD-2"), now=now + timedelta(seconds=5)
        )

        assert first.single is sample_order
        assert first.collective == ()
        assert second.single is not None
        assert second.collective == ()

    def test_trzecie_zamowienie_przelacza_na_zbiorcze(self, sample_order):
        batcher = OrderPushBatcher()
        now = utc_now()

        batcher.accept(sample_order, now=now)
        batcher.accept(replace(sample_order, external_id="ORD-2"), now=now)
        third = batcher.accept(replace(sample_order, external_id="ORD-3"), now=now)

        assert third.single is None
        assert len(third.collective) == 3

    def test_kolejne_zamowienia_rozszerzaja_zbiorcze(self, sample_order):
        """Czwarte ma dać „4 nowe zamówienia", nie osobne powiadomienie."""
        batcher = OrderPushBatcher()
        now = utc_now()

        for index in range(3):
            batcher.accept(replace(sample_order, external_id=f"ORD-{index}"), now=now)
        fourth = batcher.accept(replace(sample_order, external_id="ORD-4"), now=now)

        assert fourth.single is None
        assert len(fourth.collective) == 4

    def test_zamowienia_starsze_niz_15_minut_wypadaja_z_okna(self, sample_order):
        """
        Dwa zamówienia rano i jedno po południu to nie jest „seria" -
        trzecie ma polecieć osobno, z pełnymi danymi.
        """
        batcher = OrderPushBatcher()
        now = utc_now()

        batcher.accept(sample_order, now=now)
        batcher.accept(replace(sample_order, external_id="ORD-2"), now=now)
        late = batcher.accept(
            replace(sample_order, external_id="ORD-3"), now=now + timedelta(minutes=16)
        )

        assert late.single is not None
        assert late.collective == ()

    def test_okno_liczy_sie_ruchomo_a_nie_od_pierwszego_zamowienia(self, sample_order):
        """
        Zamówienia co 10 minut: pierwsze wypada z okna, zanim dojdzie
        trzecie, więc próg nie zostaje przekroczony.
        """
        batcher = OrderPushBatcher()
        now = utc_now()

        batcher.accept(sample_order, now=now)
        batcher.accept(replace(sample_order, external_id="ORD-2"), now=now + timedelta(minutes=10))
        third = batcher.accept(
            replace(sample_order, external_id="ORD-3"), now=now + timedelta(minutes=20)
        )

        assert third.single is not None
