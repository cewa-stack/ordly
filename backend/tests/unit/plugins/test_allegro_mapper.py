"""Testy jednostkowe mapowania JSON Allegro na encje domenowe."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from app.infrastructure.plugins.allegro.mapper import (
    map_checkout_form_to_order,
    map_customer_return_to_domain,
    map_issue_message_to_domain,
    map_issue_to_domain,
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

    def test_mapuje_dyskusje_z_przykladu_dokumentacji_allegro(self):
        """
        Payload 1:1 z przykładu 'issue-list' w oficjalnym swagger.yaml
        Allegro (GET /sale/issues, zasób beta.v1) - nie zgadywany.
        """
        raw = {
            "id": "6f552f2e-9626-46b3-af09-bfdbf9690d65",
            "type": "DISPUTE",
            "referenceNumber": None,
            "decisionDueDate": None,
            "openedDate": "2025-06-10T12:12:12.019Z",
            "subject": "nie otrzymałem towaru po wpłacie",
            "buyer": {"id": "e781964b-ed6b-4f2b-b915-6c3f7495d6ee", "login": "example-user"},
            "checkoutForm": {
                "id": "94092826-f0e2-47ca-b8d1-94fd7cb82c33",
                "createdAt": "2025-05-10T15:10:10.019Z",
            },
            "currentState": {
                "status": "DISPUTE_ONGOING",
                "statusDueDate": None,
                "returnRequired": None,
                "chatActive": True,
            },
            "chat": {
                "lastMessage": {
                    "status": "BUYER_REPLIED",
                    "createdAt": "2025-06-10T14:06:11.019Z",
                },
                "messagesCount": 2,
            },
            "description": "Zwrot 27 zł",
        }

        issue = map_issue_to_domain(raw)

        assert issue.external_id == "6f552f2e-9626-46b3-af09-bfdbf9690d65"
        assert issue.marketplace == "allegro"
        assert issue.type == "DISPUTE"
        assert issue.status == "DISPUTE_ONGOING"
        assert issue.order_external_id == "94092826-f0e2-47ca-b8d1-94fd7cb82c33"
        assert issue.buyer_login == "example-user"
        assert issue.subject == "nie otrzymałem towaru po wpłacie"
        assert issue.description == "Zwrot 27 zł"
        assert issue.messages_count == 2
        assert issue.chat_active is True
        assert issue.last_message_at is not None

    def test_mapuje_reklamacje_z_przykladu_dokumentacji_allegro(self):
        """Payload 'CLAIM' z tego samego przykładu - typ różni się od dysputy."""
        raw = {
            "id": "73cc3981-bc7e-45b2-911a-a0156871f18f",
            "type": "CLAIM",
            "referenceNumber": "1/2025",
            "openedDate": "2025-06-10T12:12:12.019Z",
            "subject": None,
            "buyer": {"id": "93975873", "login": "example-user"},
            "checkoutForm": {
                "id": "fb6f7b9a-b882-4edf-b994-9dffa6c38530",
                "createdAt": "2025-05-10T15:10:10.019Z",
            },
            "currentState": {
                "status": "CLAIM_SUBMITTED",
                "statusDueDate": "2025-06-24T12:12:12.019Z",
                "returnRequired": True,
                "chatActive": True,
            },
            "chat": {
                "lastMessage": {
                    "status": "BUYER_REPLIED",
                    "createdAt": "2025-06-10T14:06:11.019Z",
                },
                "messagesCount": 2,
            },
            "description": None,
        }

        issue = map_issue_to_domain(raw)

        assert issue.type == "CLAIM"
        assert issue.status == "CLAIM_SUBMITTED"
        assert issue.subject is None
        assert issue.description is None

    def test_mapuje_dyskusje_z_minimalnymi_danymi(self):
        """Brak opcjonalnych sekcji (chat, currentState) nie powinien wywalać błędu."""
        issue = map_issue_to_domain(
            {"id": "ISSUE-MIN", "openedDate": "2025-06-10T12:12:12.019Z"}
        )

        assert issue.external_id == "ISSUE-MIN"
        assert issue.type == "DISPUTE"
        assert issue.status == "UNKNOWN"
        assert issue.order_external_id == ""
        assert issue.buyer_login == "nieznany"
        assert issue.messages_count == 0
        assert issue.chat_active is False
        assert issue.last_message_at is None

    def test_mapuje_wiadomosc_z_przykladu_dokumentacji_allegro(self):
        """Payload 1:1 z przykładu 'chat' w swagger.yaml (GET /sale/issues/{id}/chat)."""
        raw = {
            "id": "92162836-6599-4b6f-a71e-b27392770b53",
            "text": "Proszę o wyjaśnienie problemu.",
            "author": {"login": "example-user", "role": "BUYER"},
            "createdAt": "2025-06-10T12:12:12.019Z",
        }

        message = map_issue_message_to_domain(raw)

        assert message.id == "92162836-6599-4b6f-a71e-b27392770b53"
        assert message.text == "Proszę o wyjaśnienie problemu."
        assert message.author_login == "example-user"
        assert message.author_role == "BUYER"

    def test_wiadomosc_z_pustym_loginem_autora_nie_wywraca_watku(self):
        """
        Regresja: Allegro zwraca w wątkach `"login": null` (wiadomość
        systemowa albo zanonimizowany kupujący). Wartość domyślna
        `.get(klucz, domyslna)` NIE łapie takiego przypadku - klucz
        istnieje - więc None przelatywał do encji i cały endpoint
        `/api/v1/issues/{id}/messages` zwracał 422.
        """
        message = map_issue_message_to_domain(
            {
                "id": None,
                "text": None,
                "author": {"login": None, "role": "ALLEGRO"},
                "createdAt": "2025-06-10T12:12:12.019Z",
            }
        )

        assert message.id == ""
        assert message.text == ""
        assert message.author_login == "Allegro"
        assert message.author_role == "ALLEGRO"

    def test_wiadomosci_admin_i_system_dostaja_nazwe_allegro(self):
        """
        Potwierdzone na żywych danych: moderator Allegro rozstrzygający
        spór (`ADMIN`) i automatyczne powiadomienia typu "sprzedający nie
        odpowiedział w 24h" (`SYSTEM`) też nie mają loginu.
        """
        for role in ("ADMIN", "SYSTEM"):
            message = map_issue_message_to_domain(
                {
                    "id": "M-2",
                    "text": "Sprzedający nie odpowiedział w ciągu 24 godzin.",
                    "author": {"login": None, "role": role},
                    "createdAt": "2025-06-10T12:12:12.019Z",
                }
            )
            assert message.author_login == "Allegro"
            assert message.author_role == role

    def test_wiadomosc_bez_sekcji_autora_dostaje_nazwe_zastepcza(self):
        """Brak całej sekcji `author` też nie może wywalić mapowania."""
        message = map_issue_message_to_domain(
            {"id": "M-1", "text": "cokolwiek", "createdAt": "2025-06-10T12:12:12.019Z"}
        )

        assert message.author_login == "nieznany"
        assert message.author_role == "UNKNOWN"
