"""
Status aplikacyjny i reguła priorytetu wobec Allegro - pozycje z Notion
"Brak ręcznej zmiany statusu zamówienia wyłącznie w aplikacji" oraz
"Brak jednoznacznych reguł priorytetu między statusem Allegro a statusem
aplikacyjnym" (wariant B, decyzja użytkownika 2026-10-04).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.domain.entities.order import Order
from app.domain.order_status import (
    APP_STATUS_CANCELLED,
    APP_STATUS_DONE,
    APP_STATUS_IN_PROGRESS,
    APP_STATUS_LABELS,
    APP_STATUS_NEW,
    allegro_app_status,
    app_status_label,
    effective_app_status,
    is_closed_in_app,
    is_manual_in_force,
    order_awaits_shipment,
    order_needs_new_reminder,
    order_requires_packing,
    resolve_app_status,
)

PAID = "READY_FOR_PROCESSING"


def _order(sample_order: Order, **changes) -> Order:
    base = replace(sample_order, status=PAID, fulfillment_status="NEW")
    return replace(base, **changes)


def _manual(order: Order, status: str) -> Order:
    """Ręczna zmiana tak, jak robi ją OrderStatusService (z `basis`)."""
    basis = allegro_app_status(order.status, order.fulfillment_status, order.tracking_number)
    return replace(order, app_status=status, app_status_basis=basis)


class TestNazwy:
    def test_cztery_statusy_z_notion(self):
        assert APP_STATUS_LABELS == {
            "NEW": "Nowe",
            "IN_PROGRESS": "W realizacji",
            "DONE": "Zrealizowane",
            "CANCELLED": "Anulowane",
        }
        assert app_status_label(None) == "Brak danych"


class TestStatusZAllegro:
    @pytest.mark.parametrize(
        ("status", "fulfillment", "tracking", "expected"),
        [
            (PAID, "NEW", None, APP_STATUS_NEW),
            (PAID, "PROCESSING", None, APP_STATUS_IN_PROGRESS),
            (PAID, "READY_FOR_SHIPMENT", None, APP_STATUS_IN_PROGRESS),
            (PAID, "SUSPENDED", None, APP_STATUS_IN_PROGRESS),
            (PAID, "SENT", None, APP_STATUS_DONE),
            (PAID, "PICKED_UP", None, APP_STATUS_DONE),
            (PAID, "READY_FOR_PICKUP", None, APP_STATUS_DONE),
            (PAID, "RETURNED", None, APP_STATUS_DONE),
            (PAID, "NEW", "620000123", APP_STATUS_DONE),
            ("CANCELLED", "NEW", None, APP_STATUS_CANCELLED),
            (PAID, "CANCELLED", None, APP_STATUS_CANCELLED),
            (PAID, None, None, None),
        ],
    )
    def test_mapowanie(self, status, fulfillment, tracking, expected):
        assert allegro_app_status(status, fulfillment, tracking) == expected


class TestRecznyStatus:
    def test_bez_recznej_zmiany_status_z_allegro(self, sample_order):
        order = _order(sample_order, fulfillment_status="PROCESSING")
        assert effective_app_status(order) == APP_STATUS_IN_PROGRESS
        assert not is_manual_in_force(order)

    @pytest.mark.parametrize(
        ("start_stage", "manual"),
        [
            ("NEW", APP_STATUS_IN_PROGRESS),  # Nowe -> W realizacji
            ("PROCESSING", APP_STATUS_DONE),  # W realizacji -> Zrealizowane
            ("NEW", APP_STATUS_CANCELLED),  # Nowe -> Anulowane
            ("PROCESSING", APP_STATUS_NEW),  # korekta wstecz
            ("SENT", APP_STATUS_IN_PROGRESS),  # korekta zakończonego
        ],
    )
    def test_przejscia_z_notion_i_korekty(self, sample_order, start_stage, manual):
        order = _manual(_order(sample_order, fulfillment_status=start_stage), manual)
        assert effective_app_status(order) == manual
        assert is_manual_in_force(order)

    def test_ta_sama_odpowiedz_allegro_nie_nadpisuje(self, sample_order):
        """Synchronizacja zwraca wciąż ten sam stan - ręczny zostaje."""
        order = _manual(_order(sample_order, fulfillment_status="PROCESSING"), APP_STATUS_NEW)
        again = replace(order, fulfillment_status="PROCESSING")
        assert effective_app_status(again) == APP_STATUS_NEW


class TestUzgadnianieDoPrzodu:
    def test_allegro_wysyla_po_recznym_w_realizacji(self, sample_order):
        order = _manual(_order(sample_order), APP_STATUS_IN_PROGRESS)
        sent = replace(order, fulfillment_status="SENT")
        assert effective_app_status(sent) == APP_STATUS_DONE
        assert not is_manual_in_force(sent)

    def test_numer_przesylki_tez_uzgadnia(self, sample_order):
        order = _manual(_order(sample_order), APP_STATUS_NEW)
        assert effective_app_status(replace(order, tracking_number="62000")) == APP_STATUS_DONE

    def test_allegro_nie_cofa_recznego_statusu(self, sample_order):
        """Ręcznie W realizacji; Allegro zmienia etap na NEW (wstecz) - zostaje."""
        order = _manual(_order(sample_order, fulfillment_status="READY_FOR_SHIPMENT"),
                        APP_STATUS_IN_PROGRESS)
        back = replace(order, fulfillment_status="NEW")
        assert effective_app_status(back) == APP_STATUS_IN_PROGRESS

    @pytest.mark.parametrize("stage", ["NEW", "PROCESSING", "READY_FOR_SHIPMENT", None])
    def test_zrealizowane_nie_wraca_do_nieobsluzonych(self, sample_order, stage):
        order = _manual(_order(sample_order, fulfillment_status="PROCESSING"), APP_STATUS_DONE)
        moved = replace(order, fulfillment_status=stage)
        assert effective_app_status(moved) == APP_STATUS_DONE
        assert not order_requires_packing(moved)

    @pytest.mark.parametrize("stage", ["NEW", "PROCESSING", "SENT"])
    def test_anulowane_zostaje_anulowane(self, sample_order, stage):
        order = _manual(_order(sample_order), APP_STATUS_CANCELLED)
        moved = replace(order, fulfillment_status=stage)
        assert effective_app_status(moved) == APP_STATUS_CANCELLED

    def test_d2a_zrealizowane_anulowane_przez_allegro(self, sample_order):
        order = _manual(_order(sample_order, fulfillment_status="SENT"), APP_STATUS_DONE)
        cancelled = replace(order, status="CANCELLED")
        assert effective_app_status(cancelled) == APP_STATUS_CANCELLED

    def test_resolve_czysta_funkcja(self):
        assert resolve_app_status(None, None, APP_STATUS_NEW) == APP_STATUS_NEW
        assert resolve_app_status(APP_STATUS_NEW, APP_STATUS_IN_PROGRESS,
                                  APP_STATUS_IN_PROGRESS) == APP_STATUS_NEW
        assert resolve_app_status(APP_STATUS_NEW, APP_STATUS_NEW,
                                  APP_STATUS_IN_PROGRESS) == APP_STATUS_IN_PROGRESS


class TestPowiadomienia:
    """Pozycja z Notion "Nieprawidłowa obsługa powiadomień po ręcznej zmianie statusu"."""

    @pytest.mark.parametrize("closed", [APP_STATUS_DONE, APP_STATUS_CANCELLED])
    def test_zamkniete_nie_generuja_powiadomien(self, sample_order, closed):
        order = _manual(_order(sample_order), closed)
        assert is_closed_in_app(order)
        assert not order_requires_packing(order)
        assert not order_needs_new_reminder(order)
        assert not order_awaits_shipment(order)

    def test_nowe_wymaga_obslugi_i_przypomnienia(self, sample_order):
        # Allegro ma już PROCESSING, użytkownik cofa do "Nowe".
        order = _manual(_order(sample_order, fulfillment_status="PROCESSING"), APP_STATUS_NEW)
        assert order_requires_packing(order)
        assert order_needs_new_reminder(order)

    def test_w_realizacji_widoczne_bez_alertu_20(self, sample_order):
        order = _manual(_order(sample_order), APP_STATUS_IN_PROGRESS)
        assert order_requires_packing(order)
        assert not order_needs_new_reminder(order)

    def test_bez_recznego_statusu_regula_jak_dotad(self, sample_order):
        assert order_requires_packing(_order(sample_order))
        assert order_needs_new_reminder(_order(sample_order))
        assert not order_requires_packing(_order(sample_order, fulfillment_status=None))
        assert not order_requires_packing(
            _order(sample_order, fulfillment_status="READY_FOR_SHIPMENT")
        )


class TestWyswietlanieWBocie:
    def test_reczny_status_jasno_oznaczony(self, sample_order):
        from app.domain.order_status import app_status_display

        order = _order(sample_order)
        assert app_status_display(order) == "Nowe"
        assert app_status_display(_manual(order, APP_STATUS_DONE)) == (
            "Zrealizowane (zmieniono ręcznie w aplikacji)"
        )
