"""
Mapowanie surowych struktur JSON z Allegro API na encje domenowe.

To jedyne miejsce w całym systemie, które wie, jak zbudowana jest
odpowiedź Allegro. Żaden inny moduł nie powinien znać tych szczegółów.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.domain.entities.customer import Customer
from app.domain.entities.order import Order
from app.domain.entities.order_return import OrderReturn
from app.domain.entities.product import Product
from app.domain.entities.shipment import Shipment
from app.utils.time import utc_now


def map_checkout_form_to_order(raw: dict[str, Any]) -> Order:
    """
    Mapuje pojedynczy 'checkout form' (zamówienie) z Allegro na Order.

    Args:
        raw: Surowy słownik JSON reprezentujący jedno zamówienie,
            zgodny ze strukturą zwracaną przez
            GET /order/checkout-forms.

    Returns:
        Encja domenowa Order.
    """
    buyer_raw = raw.get("buyer", {})
    customer = Customer(
        login=buyer_raw.get("login", "nieznany"),
        email=buyer_raw.get("email"),
        first_name=buyer_raw.get("firstName"),
        last_name=buyer_raw.get("lastName"),
        phone_number=buyer_raw.get("phoneNumber"),
    )

    products = [
        Product(
            external_id=line.get("offer", {}).get("id", ""),
            name=line.get("offer", {}).get("name", "nieznany produkt"),
            quantity=int(line.get("quantity", 1)),
            unit_price=Decimal(
                str(line.get("price", {}).get("amount", "0.00"))
            ),
        )
        for line in raw.get("lineItems", [])
    ]

    total_raw = raw.get("summary", {}).get("totalToPay", {})

    fulfillment_raw = raw.get("fulfillment") or {}
    fulfillment_status = fulfillment_raw.get("status")

    return Order(
        external_id=raw["id"],
        marketplace="allegro",
        buyer=customer,
        products=products,
        total_amount=Decimal(str(total_raw.get("amount", "0.00"))),
        currency=total_raw.get("currency", "PLN"),
        status=raw.get("status", "UNKNOWN"),
        order_date=_parse_datetime(raw.get("updatedAt") or raw.get("boughtAt")),
        fulfillment_status=fulfillment_status,
    )


def map_customer_return_to_domain(raw: dict[str, Any]) -> OrderReturn:
    """
    Mapuje pojedynczy 'customer return' (zwrot klienta) z Allegro na OrderReturn.

    Args:
        raw: Surowy słownik JSON reprezentujący jeden zwrot, zgodny
            ze strukturą zwracaną przez GET /order/customer-returns.

    Returns:
        Encja domenowa OrderReturn.
    """
    products = [
        Product(
            external_id=item.get("offerId", ""),
            name=item.get("name", "nieznany produkt"),
            quantity=int(item.get("quantity", 1)),
            unit_price=Decimal(str(item.get("price", {}).get("amount", "0.00"))),
        )
        for item in raw.get("items", [])
    ]

    return OrderReturn(
        external_id=raw["id"],
        marketplace="allegro",
        order_external_id=raw.get("orderId", "nieznane"),
        buyer_login=raw.get("buyer", {}).get("login", "nieznany"),
        products=products,
        status=raw.get("status", "UNKNOWN"),
        created_at=_parse_datetime(raw.get("createdAt")),
    )


def map_shipment_to_domain(order_external_id: str, raw: dict[str, Any]) -> Shipment:
    """
    Mapuje informacje o pojedynczej przesyłce z Allegro na encję Shipment.

    Args:
        order_external_id: Numer zamówienia, dla którego pobrano status.
        raw: Surowy słownik JSON z danymi pojedynczej przesyłki/paczki.

    Returns:
        Encja domenowa Shipment. Jeśli przesyłka nie ma jeszcze numeru
        listu przewozowego (waybill), pola carrier/tracking_number
        będą None, a status odzwierciedli rzeczywisty stan
        ("przygotowywana", nie "brak danych").
    """
    waybills = raw.get("waybills", [])
    first_waybill = waybills[0] if waybills else {}

    status = raw.get("status")
    if not waybills and not status:
        status = "PRZYGOTOWYWANA"

    return Shipment(
        order_external_id=order_external_id,
        carrier=first_waybill.get("carrierId"),
        tracking_number=first_waybill.get("number"),
        status=status,
        updated_at=_parse_datetime(raw.get("updatedAt")) if raw.get("updatedAt") else None,
    )


def map_shipments_list_to_domain(
    order_external_id: str, raw_shipments: list[dict[str, Any]]
) -> list[Shipment]:
    """
    Mapuje pełną listę przesyłek zamówienia (obsługa paczek podzielonych).

    Args:
        order_external_id: Numer zamówienia.
        raw_shipments: Lista surowych słowników JSON, każdy reprezentujący
            jedną przesyłkę częściową.

    Returns:
        Lista encji domenowych Shipment, jedna na każdą przesyłkę.
        Pusta lista oznacza, że sprzedawca nie nadał jeszcze niczego.
    """
    return [
        map_shipment_to_domain(order_external_id, raw) for raw in raw_shipments
    ]


def _parse_datetime(value: str | None) -> datetime:
    """
    Parsuje znacznik czasu ISO 8601 zwracany przez Allegro API.

    Wynik jest zawsze naiwnym datetime w UTC (konwencja całej bazy) -
    znaczniki z innym offsetem (np. +02:00) są najpierw przeliczane
    na UTC, a dopiero potem pozbawiane tzinfo.
    """
    if value is None:
        return utc_now()
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed
