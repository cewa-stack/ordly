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
from app.domain.entities.issue import Issue, IssueMessage
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
            unit_price=Decimal(str(line.get("price", {}).get("amount", "0.00"))),
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


def map_issue_to_domain(raw: dict[str, Any]) -> Issue:
    """
    Mapuje pojedynczy 'post purchase issue' (dyskusję lub reklamację)
    z Allegro na Issue.

    Args:
        raw: Surowy słownik JSON zgodny ze strukturą zwracaną przez
            GET /sale/issues (zasób beta.v1, zastąpił dawne
            GET /sale/disputes - patrz komentarz w Issue).

    Returns:
        Encja domenowa Issue.
    """
    current_state = raw.get("currentState") or {}
    chat = raw.get("chat") or {}
    last_message = chat.get("lastMessage") or {}
    last_message_created_at = last_message.get("createdAt")

    return Issue(
        external_id=raw["id"],
        marketplace="allegro",
        type=raw.get("type") or "DISPUTE",
        status=current_state.get("status") or "UNKNOWN",
        order_external_id=(raw.get("checkoutForm") or {}).get("id") or "",
        buyer_login=(raw.get("buyer") or {}).get("login") or "nieznany",
        subject=raw.get("subject"),
        description=raw.get("description"),
        opened_at=_parse_datetime(raw.get("openedDate")),
        messages_count=int(chat.get("messagesCount") or 0),
        chat_active=bool(current_state.get("chatActive", False)),
        last_message_at=(
            _parse_datetime(last_message_created_at) if last_message_created_at else None
        ),
    )


def map_issue_message_to_domain(raw: dict[str, Any]) -> IssueMessage:
    """
    Mapuje pojedynczą wiadomość z GET /sale/issues/{id}/chat na IssueMessage.

    Wszystkie pola tekstowe są ściągane przez `or`, nie przez wartość
    domyślną `.get(klucz, domyslna)` - Allegro zwraca w wątkach klucze
    obecne, ale ustawione na `null` (np. `author.login` przy wiadomości
    systemowej albo po anonimizacji kupującego). Wartość domyślna
    `.get()` działa tylko przy BRAKU klucza, więc `null` przelatywał do
    encji i cały wątek wywracał się na walidacji `IssueMessageOut`
    błędem 422 - dla użytkownika wyglądało to jak "dyskusje się nie
    ładują po kliknięciu".

    Args:
        raw: Surowy słownik JSON reprezentujący jedną wiadomość w wątku.

    Returns:
        Encja domenowa IssueMessage.
    """
    author = raw.get("author") or {}
    return IssueMessage(
        id=raw.get("id") or "",
        text=raw.get("text") or "",
        author_login=author.get("login") or _author_fallback_login(author.get("role")),
        author_role=author.get("role") or "UNKNOWN",
        created_at=_parse_datetime(raw.get("createdAt")),
    )


def _author_fallback_login(role: str | None) -> str:
    """
    Nazwa zastępcza autora wiadomości, gdy Allegro nie podaje loginu.

    Bez tego wiadomości systemowe pokazywałyby się jako "nieznany",
    co sugeruje błąd - a to normalny stan (Allegro nie ma loginu dla
    własnych komunikatów w wątku). `ADMIN` i `SYSTEM` potwierdzone na
    żywych danych - moderator Allegro rozstrzygający spór i automatyczne
    powiadomienia ("sprzedający nie odpowiedział w 24h") też nie mają
    loginu.
    """
    if role in ("ALLEGRO", "ADMIN", "SYSTEM"):
        return "Allegro"
    if role == "SELLER":
        return "Ty"
    if role == "BUYER":
        return "Kupujący"
    return "nieznany"


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
    return [map_shipment_to_domain(order_external_id, raw) for raw in raw_shipments]


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
