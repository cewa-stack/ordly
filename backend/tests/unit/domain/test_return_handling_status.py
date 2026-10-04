"""
Statusy obsługi zwrotów - pozycja z Notion "Podział zwrotów i anulowanych
zamówień na osobne podzakładki oraz statusy obsługi" (D6-a: dla zwrotów
automatycznie z Allegro).
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.api.schemas import return_out
from app.domain.entities.order_return import ReturnRecord
from app.domain.returns import return_handling_status, return_requires_action


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("CREATED", "REPORTED"),
        ("DISPATCHED", "IN_PROGRESS"),
        ("IN_TRANSIT", "IN_PROGRESS"),
        ("DELIVERED", "IN_PROGRESS"),
        ("WAREHOUSE_DELIVERED", "IN_PROGRESS"),
        ("WAREHOUSE_VERIFICATION", "IN_PROGRESS"),
        ("FINISHED", "DONE"),
        ("FINISHED_APT", "DONE"),
        ("COMMISSION_REFUND_CLAIMED", "DONE"),
        ("COMMISSION_REFUNDED", "DONE"),
        ("REJECTED", "DONE"),
        ("CANCELLED", "DONE"),
        ("NIEZNANY_STATUS", "REPORTED"),
    ],
)
def test_mapowanie_statusow_allegro(status, expected):
    assert return_handling_status(status) == expected


def test_anulowane_zamowienie_zamyka_zwrot():
    assert return_handling_status("CREATED", "CANCELLED") == "DONE"


@pytest.mark.parametrize("status", ["CREATED", "IN_TRANSIT", "FINISHED", "REJECTED"])
def test_zakonczony_dokladnie_wtedy_gdy_nie_wymaga_dzialania(status):
    assert (return_handling_status(status) == "DONE") is (not return_requires_action(status))


def test_api_zwraca_status_obslugi_z_nazwa():
    record = ReturnRecord(
        external_id="R1",
        marketplace="allegro",
        order_external_id="O1",
        buyer_login="anna_k",
        status="IN_TRANSIT",
        products_summary="Kubek x1",
        return_date=datetime(2026, 9, 1),
    )
    out = return_out(record)
    assert out.handling_status == "IN_PROGRESS"
    assert out.handling_label == "W trakcie realizacji"
