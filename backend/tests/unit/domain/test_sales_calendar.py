"""
Testy kalendarza sprzedażowego.

Ten moduł jest bliźniakiem `desktop/src/renderer/src/lib/salesCalendar.ts`,
a konwencja dnia tygodnia różni się między nimi (`date.weekday()` liczy od
poniedziałku, `Date.getDay()` od niedzieli) - dlatego daty ruchome mają tu
twarde asercje na znane, sprawdzalne dni.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.domain.sales_calendar import (
    SALES_EVENTS,
    build_calendar,
    easter_sunday,
    upcoming_events,
)


def _instance(year: int, event_id: str):
    return next(
        i for i in build_calendar([year]) if i.definition.id == event_id
    )


class TestEasterSunday:
    def test_zwraca_znane_daty_wielkanocy(self):
        assert easter_sunday(2024) == date(2024, 3, 31)
        assert easter_sunday(2025) == date(2025, 4, 20)
        assert easter_sunday(2026) == date(2026, 4, 5)
        assert easter_sunday(2027) == date(2027, 3, 28)

    def test_swieta_ruchome_sa_liczone_od_wielkanocy(self):
        """Boże Ciało to zawsze czwartek 60 dni po Wielkanocy."""
        boze_cialo = _instance(2026, "boze-cialo")

        assert boze_cialo.peak == date(2026, 6, 4)
        assert boze_cialo.peak.weekday() == 3


class TestDatyRuchome:
    def test_black_friday_to_ostatni_piatek_listopada(self):
        """Sprawdza też rok, w którym listopad ma piąty piątek."""
        assert _instance(2025, "black-friday").peak == date(2025, 11, 28)
        assert _instance(2026, "black-friday").peak == date(2026, 11, 27)
        assert _instance(2024, "black-friday").peak == date(2024, 11, 29)

    def test_cyber_monday_wypada_trzy_dni_po_black_friday(self):
        cyber_monday = _instance(2026, "cyber-monday")

        assert cyber_monday.peak == date(2026, 11, 30)
        assert cyber_monday.peak.weekday() == 0


class TestOknoWydarzenia:
    def test_okres_przygotowan_zaczyna_sie_lead_days_przed_szczytem(self):
        boze_narodzenie = _instance(2026, "boze-narodzenie")

        assert boze_narodzenie.peak == date(2026, 12, 24)
        assert boze_narodzenie.prep_start == date(2026, 11, 19)
        assert boze_narodzenie.tail_end == date(2026, 12, 26)

    def test_status_rozroznia_trwa_nadchodzi_i_minelo(self):
        walentynki = _instance(2026, "walentynki")

        assert walentynki.status(date(2026, 1, 10)) == "nadchodzi"
        assert walentynki.status(date(2026, 2, 1)) == "trwa"
        assert walentynki.status(date(2026, 3, 1)) == "minelo"


class TestUpcomingEvents:
    def test_pomija_wydarzenia_ktore_juz_sie_skonczyly(self):
        """Powrót do szkoły ma ogon do końca sierpnia - we wrześniu już go nie ma."""
        ids = {e.definition.id for e in upcoming_events(date(2026, 9, 6), days_ahead=120)}

        assert "wakacje-powrot-do-szkoly-start" not in ids
        assert "black-friday" in ids

    def test_pomija_wydarzenia_za_horyzontem(self):
        ids = {e.definition.id for e in upcoming_events(date(2026, 9, 6), days_ahead=30)}

        assert ids == set()

    def test_siega_do_nastepnego_roku(self):
        """W grudniu trzeba widzieć styczniowe i lutowe okresy sprzedażowe."""
        ids = {e.definition.id for e in upcoming_events(date(2026, 12, 20), days_ahead=70)}

        assert "walentynki" in ids
        assert "nowy-rok" in ids

    def test_wynik_jest_posortowany_po_dacie_szczytu(self):
        events = upcoming_events(date(2026, 10, 1), days_ahead=120)

        assert [e.peak for e in events] == sorted(e.peak for e in events)

    def test_wydarzenie_w_trakcie_okna_przygotowan_jest_widoczne(self):
        """Black Friday 2026: okno startuje 6 listopada (21 dni przed 27.11)."""
        events = upcoming_events(date(2026, 11, 10), days_ahead=30)
        black_friday = next(e for e in events if e.definition.id == "black-friday")

        assert black_friday.status(date(2026, 11, 10)) == "trwa"


class TestDefinicje:
    def test_kazde_wydarzenie_ma_dokladnie_jedno_zrodlo_daty(self):
        for definition in SALES_EVENTS:
            sources = [
                definition.fixed_date is not None,
                definition.nth_weekday is not None,
                definition.easter_offset is not None,
            ]
            assert sum(sources) == 1, f"{definition.id} ma {sum(sources)} źródeł daty"

    def test_identyfikatory_sa_unikalne(self):
        ids = [definition.id for definition in SALES_EVENTS]

        assert len(ids) == len(set(ids))

    def test_okno_wydarzenia_nigdy_nie_jest_odwrocone(self):
        for instance in build_calendar([2025, 2026, 2027]):
            assert instance.prep_start <= instance.peak <= instance.tail_end

    def test_swieta_nie_maja_okresu_przygotowan(self):
        """Dzień wolny to informacja o logistyce, nie okazja do wystawiania ofert."""
        for definition in SALES_EVENTS:
            if definition.category == "swieto":
                assert definition.lead_days == 0, definition.id

    def test_kalendarz_obejmuje_wszystkie_podane_lata(self):
        instances = build_calendar([2026, 2027])

        assert len(instances) == len(SALES_EVENTS) * 2
        assert instances[-1].peak - instances[0].peak > timedelta(days=365)
