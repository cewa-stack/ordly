"""Testy jednostkowe mapowania JSON Allegro na encje domenowe."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from app.infrastructure.plugins.allegro.mapper import (
    map_checkout_form_to_order,
    map_customer_return_to_domain,
    map_shipment_to_domain,
)

_FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "allegro_responses"


class TestAllegroMapper:
    """Testy poprawności mapowania surowych odpowiedzi Allegro API."""

    def test_mapuje_pelne_zamowienie_z_przykladowego_jsona(self):
        """Sprawdza mapowanie wszystkich kluczowych pól zamówienia."""
        raw = json.loads((_FIXTURES_DIR / "checkout_form_sample.json").read_text())

        order = map_checkout_form_to_order(raw)

        assert order.external_id == "ABC123-DEF456"
        assert order.marketplace == "allegro"
        assert order.buyer.login == "kupujacy_testowy"
        assert order.buyer.email == "kupujacy@example.com"
        assert order.total_amount == Decimal("51.00")
        assert order.currency == "PLN"
        assert len(order.products) == 1
        assert order.products[0].name == "Testowy produkt A"
        assert order.products[0].quantity == 2

    def test_mapuje_zamowienie_bez_email_kupujacego(self):
        """Brak opcjonalnych pól (np. email) nie powinien powodować błędu."""
        raw = {
            "id": "MINIMAL-1",
            "status": "NEW",
            "buyer": {"login": "tylko_login"},
            "lineItems": [],
            "summary": {"totalToPay": {"amount": "10.00", "currency": "PLN"}},
        }

        order = map_checkout_form_to_order(raw)

        assert order.buyer.login == "tylko_login"
        assert order.buyer.email is None
        assert order.products == []

    def test_mapuje_status_realizacji_i_telefon(self):
        """fulfillment.status oraz phoneNumber kupującego powinny być mapowane."""
        raw = {
            "id": "FUL-1",
            "status": "READY_FOR_PROCESSING",
            "fulfillment": {"status": "PROCESSING"},
            "buyer": {"login": "kupujacy", "phoneNumber": "+48555111222"},
            "lineItems": [],
            "summary": {"totalToPay": {"amount": "10.00", "currency": "PLN"}},
        }

        order = map_checkout_form_to_order(raw)

        assert order.fulfillment_status == "PROCESSING"
        assert order.buyer.phone_number == "+48555111222"

    def test_brak_sekcji_fulfillment_daje_none(self):
        """Zamówienie bez sekcji fulfillment powinno mieć fulfillment_status None."""
        raw = {
            "id": "NO-FUL-1",
            "status": "NEW",
            "buyer": {"login": "kupujacy"},
            "lineItems": [],
            "summary": {"totalToPay": {"amount": "10.00", "currency": "PLN"}},
        }

        order = map_checkout_form_to_order(raw)

        assert order.fulfillment_status is None

    def test_przesylka_bez_waybills_ma_status_przygotowywana(self):
        """Zamówienie bez nadanej paczki powinno mieć status PRZYGOTOWYWANA."""
        shipment = map_shipment_to_domain("ORDER-1", {"waybills": [], "status": None})

        assert shipment.status == "PRZYGOTOWYWANA"
        assert shipment.tracking_number is None

    def test_przesylka_z_waybill_mapuje_numer_i_przewoznika(self):
        """Przesyłka z jednym waybillem powinna poprawnie zmapować przewoźnika i numer."""
        raw = {
            "waybills": [{"carrierId": "DPD", "number": "1234567890"}],
            "status": "SENT",
            "updatedAt": "2026-07-02T08:00:00Z",
        }

        shipment = map_shipment_to_domain("ORDER-1", raw)

        assert shipment.carrier == "DPD"
        assert shipment.tracking_number == "1234567890"
        assert shipment.status == "SENT"

    def test_mapuje_zwrot_klienta_z_pelnymi_danymi(self):
        """Sprawdza mapowanie wszystkich kluczowych pól zwrotu klienta."""
        raw = {
            "id": "RETURN-XYZ",
            "orderId": "ABC123-DEF456",
            "buyer": {"login": "kupujacy_testowy"},
            "items": [
                {
                    "offerId": "OFFER-1",
                    "name": "Testowy produkt A",
                    "quantity": 2,
                    "price": {"amount": "25.50", "currency": "PLN"},
                }
            ],
            "status": "CREATED",
            "createdAt": "2026-07-02T10:00:00Z",
        }

        order_return = map_customer_return_to_domain(raw)

        assert order_return.external_id == "RETURN-XYZ"
        assert order_return.marketplace == "allegro"
        assert order_return.order_external_id == "ABC123-DEF456"
        assert order_return.buyer_login == "kupujacy_testowy"
        assert order_return.status == "CREATED"
        assert len(order_return.products) == 1
        assert order_return.products[0].name == "Testowy produkt A"
        assert order_return.products[0].quantity == 2
        assert order_return.products[0].unit_price == Decimal("25.50")
        assert "Testowy produkt A x2" in order_return.products_summary

    def test_mapuje_zwrot_z_minimalnymi_danymi(self):
        """Brak opcjonalnych pól zwrotu nie powinien powodować błędu."""
        order_return = map_customer_return_to_domain({"id": "RETURN-MIN"})

        assert order_return.external_id == "RETURN-MIN"
        assert order_return.order_external_id == "nieznane"
        assert order_return.buyer_login == "nieznany"
        assert order_return.status == "UNKNOWN"
        assert order_return.products == []
        assert order_return.products_summary == "brak danych"
