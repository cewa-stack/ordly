"""
Znaczniki czasu w JSON-ie API muszą nieść strefę.

Zgłoszony objaw: w desktopie i na telefonie godziny były cofnięte o dwie
(latem). Baza trzyma czas w UTC, API wysyłało go bez strefy, a JavaScript
czyta taki napis jako czas lokalny.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.api.schemas import event_out
from app.repositories.sqlite_event_repository import EventRecord


def _payload(created_at: datetime) -> str:
    record = EventRecord(event_type="OrderCreated", level="INFO", created_at=created_at)
    return event_out(record).model_dump_json()


class TestZnacznikiCzasu:
    def test_naiwny_czas_z_bazy_wychodzi_jako_utc_z_oznaczeniem_strefy(self):
        assert '"created_at":"2026-09-13T17:13:00.000Z"' in _payload(
            datetime(2026, 9, 13, 17, 13)
        )

    def test_mikrosekundy_sa_skracane_do_milisekund(self):
        """Safari w PWA nie gwarantuje odczytu ułamka dłuższego niż 3 cyfry."""
        assert '"created_at":"2026-09-13T17:13:05.123Z"' in _payload(
            datetime(2026, 9, 13, 17, 13, 5, 123456)
        )

    def test_czas_ze_strefa_jest_przeliczany_na_utc(self):
        warsaw = datetime(2026, 9, 13, 19, 13, tzinfo=ZoneInfo("Europe/Warsaw"))
        assert '"created_at":"2026-09-13T17:13:00.000Z"' in _payload(warsaw)
