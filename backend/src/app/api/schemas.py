"""
Schematy Pydantic dla ORDLY API (aplikacja mobilna ORDLY Mobile).

Zasada: schematy tylko opisują kształt JSON i mapują encje domenowe na
odpowiedź HTTP (funkcje `*_out`) - żadnej logiki biznesowej. Logika żyje
wyłącznie w serwisach (`app/services/`), tak jak dla bota Telegram.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, PlainSerializer, field_validator

from app.domain.entities.issue import Issue, IssueMessage
from app.domain.entities.mail_message import MailMessage
from app.domain.entities.marketplace_offer import MarketplaceOffer
from app.domain.entities.offer_stock_movement import OfferStockMovement
from app.domain.entities.order import Order
from app.domain.entities.order_return import ReturnRecord
from app.domain.entities.ordlak_conversation import OrdlakConversation
from app.domain.entities.shipment import Shipment
from app.infrastructure.mail.mime import MailBodies, html_to_plain_text
from app.repositories.sqlite_event_repository import EventRecord
from app.services.dashboard_service import DashboardSummary
from app.services.mailbox_service import MailboxStatus
from app.services.ordlak_assistant_service import ChatResult
from app.shared.dto.offer_catalog_dto import CatalogSyncResult
from app.shared.dto.stats_dto import HealthStatus, StatsSummary, SyncResult

#: Kwota pieniężna w odpowiedzi API - w Pythonie dalej `Decimal` (dokładne
#: sumowanie i zaokrąglanie), ale w JSON-ie ZAWSZE liczba, nigdy string.
#:
#: Pydantic v2 domyślnie serializuje `Decimal` do stringa ("19.99"), żeby nie
#: stracić precyzji. Klienci brali to za liczbę i sumowali: `0 + "19.99"` w
#: JavaScripcie to sklejenie tekstu, więc druga pozycja dawała "019.9919.99",
#: a `Intl.NumberFormat` pokazywał z tego `NaN zł` (ekran Statystyki,
#: "Najczęściej sprzedawane"). Kwoty w tej aplikacji mieszczą się w groszach,
#: więc float w JSON-ie nic nie psuje, a usuwa całą klasę tego błędu.
Money = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]


def _utc_iso(value: datetime) -> str:
    """Czas z bazy (naiwny UTC) jako ISO 8601 z jawnym `Z` i milisekundami."""
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return aware.isoformat(timespec="milliseconds").replace("+00:00", "Z")


#: Znacznik czasu w odpowiedzi API - ZAWSZE z oznaczeniem strefy (`...Z`).
#:
#: Baza trzyma naiwne datetime w UTC, a Pydantic serializował je bez strefy
#: ("2026-09-13T17:13:00"). JavaScript czyta taki napis jako czas LOKALNY,
#: więc desktop i telefon pokazywały każdą godzinę cofniętą o różnicę do
#: UTC - latem o dwie godziny: zamówienie z 19:13 widniało jako 17:13,
#: a mail sprzed minuty jako "2 godz.". Milisekundy zamiast mikrosekund,
#: bo Safari (PWA na iPhonie) nie gwarantuje odczytu dłuższych ułamków.
UtcDatetime = Annotated[
    datetime, PlainSerializer(_utc_iso, return_type=str, when_used="json")
]


# --------------------------------------------------------------------------
# Logowanie
# --------------------------------------------------------------------------


class LoginIn(BaseModel):
    """Ciało żądania `POST /api/v1/auth/login`."""

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginOut(BaseModel):
    """
    Odpowiedź `POST /api/v1/auth/login` - token identyczny z tym, którego
    oczekuje `require_api_token` na reszcie ORDLY API, więc aplikacja
    mobilna używa go bez żadnej dodatkowej logiki.
    """

    token: str


# --------------------------------------------------------------------------
# Zamówienia
# --------------------------------------------------------------------------


class OrderProductOut(BaseModel):
    """Pojedyncza pozycja (produkt) w zamówieniu."""

    external_id: str
    name: str
    quantity: int
    unit_price: Money
    total_price: Money


class OrderOut(BaseModel):
    """Zamówienie zwracane przez `/api/v1/orders`."""

    external_id: str
    marketplace: str
    buyer_login: str
    total_amount: Money
    currency: str
    status: str
    fulfillment_status: str | None
    tracking_number: str | None
    order_date: UtcDatetime
    products: list[OrderProductOut]


def order_out(order: Order) -> OrderOut:
    """Mapuje encję domenową `Order` na schemat odpowiedzi API."""
    return OrderOut(
        external_id=order.external_id,
        marketplace=order.marketplace,
        buyer_login=order.buyer.login,
        total_amount=order.total_amount,
        currency=order.currency,
        status=order.status,
        fulfillment_status=order.fulfillment_status,
        tracking_number=order.tracking_number,
        order_date=order.order_date,
        products=[
            OrderProductOut(
                external_id=p.external_id,
                name=p.name,
                quantity=p.quantity,
                unit_price=p.unit_price,
                total_price=p.total_price,
            )
            for p in order.products
        ],
    )


class ShipmentOut(BaseModel):
    """Status przesyłki zwracany przez `/api/v1/orders/{id}/tracking`."""

    order_external_id: str
    carrier: str | None
    tracking_number: str | None
    status: str | None
    updated_at: UtcDatetime | None


def shipment_out(shipment: Shipment) -> ShipmentOut:
    """Mapuje encję domenową `Shipment` na schemat odpowiedzi API."""
    return ShipmentOut(
        order_external_id=shipment.order_external_id,
        carrier=shipment.carrier,
        tracking_number=shipment.tracking_number,
        status=shipment.status,
        updated_at=shipment.updated_at,
    )


class FulfillmentStatusIn(BaseModel):
    """
    Ciało żądania `POST /api/v1/orders/{id}/fulfillment`.

    Dozwolone wartości to dokładnie te, które przyjmuje Allegro -
    `Literal` zamiast `str` sprawia, że literówka wraca jako 422
    z listą poprawnych opcji, a nie jako 502 z marketplace.
    """

    status: Literal["NEW", "PROCESSING", "READY_FOR_SHIPMENT", "SENT", "PICKED_UP"]


class SyncResultOut(BaseModel):
    """Wynik synchronizacji zwracany przez `POST /api/v1/orders/sync`."""

    new_orders_count: int
    checked_orders_count: int
    cancelled_orders_count: int
    new_returns_count: int


def sync_result_out(result: SyncResult) -> SyncResultOut:
    """Mapuje `SyncResult` na schemat odpowiedzi API (bez pełnych list encji)."""
    return SyncResultOut(
        new_orders_count=result.new_orders_count,
        checked_orders_count=result.checked_orders_count,
        cancelled_orders_count=len(result.cancelled_orders),
        new_returns_count=len(result.new_returns),
    )


# --------------------------------------------------------------------------
# Zwroty
# --------------------------------------------------------------------------


class ReturnOut(BaseModel):
    """Zwrot klienta zwracany przez `GET /api/v1/returns`."""

    external_id: str
    marketplace: str
    order_external_id: str
    buyer_login: str
    status: str
    products_summary: str
    return_date: UtcDatetime


def return_out(record: ReturnRecord) -> ReturnOut:
    """Mapuje ReturnRecord (odczyt z repozytorium) na schemat odpowiedzi API."""
    return ReturnOut(
        external_id=record.external_id,
        marketplace=record.marketplace,
        order_external_id=record.order_external_id,
        buyer_login=record.buyer_login,
        status=record.status,
        products_summary=record.products_summary,
        return_date=record.return_date,
    )


# --------------------------------------------------------------------------
# Dyskusje i reklamacje
# --------------------------------------------------------------------------


class IssueOut(BaseModel):
    """Dyskusja lub reklamacja zwracana przez `GET /api/v1/issues`."""

    external_id: str
    marketplace: str
    type: str
    status: str
    order_external_id: str
    buyer_login: str
    subject: str | None
    description: str | None
    opened_at: UtcDatetime
    messages_count: int
    chat_active: bool
    last_message_at: UtcDatetime | None


def issue_out(issue: Issue) -> IssueOut:
    """Mapuje encję domenową Issue na schemat odpowiedzi API."""
    return IssueOut(
        external_id=issue.external_id,
        marketplace=issue.marketplace,
        type=issue.type,
        status=issue.status,
        order_external_id=issue.order_external_id,
        buyer_login=issue.buyer_login,
        subject=issue.subject,
        description=issue.description,
        opened_at=issue.opened_at,
        messages_count=issue.messages_count,
        chat_active=issue.chat_active,
        last_message_at=issue.last_message_at,
    )


class IssueMessageOut(BaseModel):
    """Pojedyncza wiadomość zwracana przez `GET /api/v1/issues/{id}/messages`."""

    id: str
    text: str
    author_login: str
    author_role: str
    created_at: UtcDatetime


def issue_message_out(message: IssueMessage) -> IssueMessageOut:
    """Mapuje encję domenową IssueMessage na schemat odpowiedzi API."""
    return IssueMessageOut(
        id=message.id,
        text=message.text,
        author_login=message.author_login,
        author_role=message.author_role,
        created_at=message.created_at,
    )


class IssueReplyIn(BaseModel):
    """Ciało żądania `POST /api/v1/issues/{id}/reply`."""

    text: str = Field(min_length=1, max_length=20000)


# --------------------------------------------------------------------------
# Mail do hurtowni
# --------------------------------------------------------------------------


class WholesalerMailIn(BaseModel):
    """Ciało żądania `POST /api/v1/mail/send-wholesaler-order`."""

    to: str = Field(min_length=3, max_length=320)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20000)

    @field_validator("to")
    @classmethod
    def validate_email_shape(cls, value: str) -> str:
        """Prosta walidacja kształtu adresu - pełna walidacja RFC nie jest tu potrzebna."""
        local_part, _, domain_part = value.partition("@")
        if not local_part or "." not in domain_part or domain_part.startswith("."):
            raise ValueError("Nieprawidłowy adres e-mail")
        return value


# --------------------------------------------------------------------------
# Skrzynka
# --------------------------------------------------------------------------


class MailMessageOut(BaseModel):
    """Mail od marketplace zwracany przez `GET /api/v1/mail/messages`."""

    message_id: str
    sender: str
    subject: str
    received_at: UtcDatetime
    source: str
    body_preview: str
    is_read: bool


def mail_message_out(message: MailMessage) -> MailMessageOut:
    """Mapuje encję domenową MailMessage na schemat odpowiedzi API."""
    return MailMessageOut(
        message_id=message.message_id,
        sender=message.sender,
        subject=message.subject,
        received_at=message.received_at,
        source=message.source,
        body_preview=message.body_preview,
        is_read=message.is_read,
    )


class MailBodyOut(BaseModel):
    """
    Pełna treść maila z `GET /api/v1/mail/messages/{message_id}/body`.

    Dwa osobne pola, nie jeden sklejony string: aplikacja świadomie
    wybiera, co pokazać - `html_body` idzie do izolowanego `<iframe>`,
    a `plain_body` jest wariantem zapasowym dla widoków, które HTML-a
    nie renderują.
    """

    html_body: str | None
    plain_body: str | None


def mail_body_out(bodies: MailBodies) -> MailBodyOut:
    """
    Mapuje treść maila na schemat odpowiedzi API.

    `plain_body` NIGDY nie jest puste, jeśli mail ma jakąkolwiek treść:
    gdy brakuje części `text/plain` (a Allegro często wysyła sam HTML),
    powstaje z HTML-a. Dzięki temu żaden klient nie musi mieć własnego
    "co pokazać, gdy nie ma tekstu" - a to właśnie brak tego wariantu
    kończył się linkiem "otwórz w Gmailu" jako jedyną drogą do treści.
    """
    plain = bodies.text if bodies.text and bodies.text.strip() else None
    if plain is None and bodies.html:
        plain = html_to_plain_text(bodies.html)
    return MailBodyOut(html_body=bodies.html, plain_body=plain)


class MailboxStatusOut(BaseModel):
    """Stan skrzynki zwracany przez `GET /api/v1/mail/status`."""

    configured: bool
    host: str
    user_masked: str
    watch_senders: list[str]
    message_count: int
    last_received_at: UtcDatetime | None


def mailbox_status_out(status: MailboxStatus) -> MailboxStatusOut:
    """Mapuje stan skrzynki z serwisu na schemat odpowiedzi API."""
    return MailboxStatusOut(
        configured=status.configured,
        host=status.host,
        user_masked=status.user_masked,
        watch_senders=status.watch_senders,
        message_count=status.message_count,
        last_received_at=status.last_received_at,
    )


class MailSyncResultOut(BaseModel):
    """Wynik ręcznej synchronizacji skrzynki (`POST /api/v1/mail/sync`)."""

    new_count: int
    configured: bool


# --------------------------------------------------------------------------
# Ordlak (asystent AI)
# --------------------------------------------------------------------------


class OrdlakStatusOut(BaseModel):
    """
    Stan modułu Ordlak (`GET /api/v1/ordlak/status`).

    Pozwala ekranowi powiedzieć wprost "brak klucza API na Pi" zamiast
    czekać, aż użytkownik wyśle pytanie i dostanie błąd - ta sama zasada
    co przy `GET /api/v1/mail/status`.
    """

    configured: bool
    model: str


class OrdlakChatIn(BaseModel):
    """
    Ciało żądania `POST /api/v1/ordlak/chat` - JEDNO pytanie.

    Historia rozmowy żyje w bazie na Pi, więc aplikacja nie przysyła
    kontekstu: podaje `conversation_id` istniejącego wątku albo pomija go,
    żeby zacząć nowy.
    """

    message: str = Field(min_length=1, max_length=8000)
    conversation_id: int | None = None


class OrdlakChatOut(BaseModel):
    """
    Odpowiedź asystenta.

    `used_tools` to nazwy narzędzi, z których model faktycznie odczytał
    dane - aplikacja pokazuje je pod odpowiedzią, żeby było widać, że
    liczby wzięły się z bazy, a nie z modelu.
    """

    conversation_id: int
    reply: str
    used_tools: list[str]


class OrdlakMessageOut(BaseModel):
    """Zapisana wypowiedź w wątku."""

    role: Literal["user", "assistant"]
    content: str
    created_at: UtcDatetime
    used_tools: list[str]


class OrdlakConversationOut(BaseModel):
    """
    Wątek rozmowy. Na liście `messages` jest puste - pełną historię
    oddaje dopiero `GET /api/v1/ordlak/conversations/{id}`.
    """

    id: int
    title: str
    created_at: UtcDatetime
    updated_at: UtcDatetime
    message_count: int
    messages: list[OrdlakMessageOut]


def ordlak_chat_out(result: ChatResult) -> OrdlakChatOut:
    """Mapuje wynik `OrdlakAssistantService.ask` na schemat odpowiedzi."""
    return OrdlakChatOut(
        conversation_id=result.conversation_id,
        reply=result.reply,
        used_tools=list(result.used_tools),
    )


def ordlak_conversation_out(conversation: OrdlakConversation) -> OrdlakConversationOut:
    """Mapuje wątek rozmowy na schemat odpowiedzi API."""
    return OrdlakConversationOut(
        id=conversation.id or 0,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=conversation.message_count,
        messages=[
            OrdlakMessageOut(
                role=message.role,
                content=message.content,
                created_at=message.created_at,
                used_tools=list(message.used_tools),
            )
            for message in conversation.messages
        ],
    )


# --------------------------------------------------------------------------
# Magazyn
# --------------------------------------------------------------------------


class OfferOut(BaseModel):
    """
    Oferta wystawiona na marketplace - pozycja magazynu ORDLY.

    `available_stock` i `quantity_on_hand` to dwie różne liczby i obie
    są tu celowo: pierwsza mówi, ile sztuk obiecuje oferta kupującym
    (pochodzi z API), druga - ile ich naprawdę leży na półce (wpisana
    ręcznie). Rozjazd między nimi jest informacją, nie błędem.
    """

    marketplace: str
    external_id: str
    name: str
    signature: str | None
    status: str
    available_stock: int
    sold_count: int
    price: Money | None
    image_url: str | None
    synced_at: UtcDatetime | None

    #: `null` znaczy "nigdy nie wpisano" i jest czymś innym niż 0
    #: ("sprawdziłem, nie ma") - interfejs pokazuje w tym miejscu kreskę.
    quantity_on_hand: int | None


def offer_out(offer: MarketplaceOffer) -> OfferOut:
    """Mapuje encję domenową `MarketplaceOffer` na schemat odpowiedzi API."""
    return OfferOut(
        marketplace=offer.marketplace,
        external_id=offer.external_id,
        name=offer.name,
        signature=offer.signature,
        status=offer.status,
        available_stock=offer.available_stock,
        sold_count=offer.sold_count,
        price=offer.price,
        image_url=offer.image_url,
        synced_at=offer.synced_at,
        quantity_on_hand=offer.quantity_on_hand,
    )


class OfferQuantityIn(BaseModel):
    """
    Ciało żądania `PUT /api/v1/stock/offers/{marketplace}/{id}/quantity`.

    Zawsze ustawienie wartości, nigdy "dodaj"/"odejmij": ilość bierze się
    tu z policzenia towaru na półce, a nie z operacji na poprzedniej
    liczbie, której i tak nikt nie pilnował.
    """

    quantity: int = Field(ge=0)
    reason: str = Field(default="Inwentaryzacja", min_length=1, max_length=255)


class OfferMovementOut(BaseModel):
    """Wpis historii ręcznych zmian ilości przy ofercie."""

    #: `null` przy pierwszym wpisie - nie było od czego liczyć różnicy.
    change: int | None
    quantity_after: int
    reason: str
    occurred_at: UtcDatetime


def offer_movement_out(movement: OfferStockMovement) -> OfferMovementOut:
    """Mapuje `OfferStockMovement` na schemat odpowiedzi API."""
    return OfferMovementOut(
        change=movement.change,
        quantity_after=movement.quantity_after,
        reason=movement.reason,
        occurred_at=movement.occurred_at,
    )


class CatalogSyncOut(BaseModel):
    """Podsumowanie `POST /api/v1/stock/sync`."""

    marketplace: str
    fetched: int
    added: int
    removed: int
    synced_at: UtcDatetime


def catalog_sync_out(result: CatalogSyncResult) -> CatalogSyncOut:
    """Mapuje `CatalogSyncResult` na schemat odpowiedzi API."""
    return CatalogSyncOut(
        marketplace=result.marketplace,
        fetched=result.fetched,
        added=result.added,
        removed=result.removed,
        synced_at=result.synced_at,
    )


# --------------------------------------------------------------------------
# Statystyki, zdrowie, dashboard, logi
# --------------------------------------------------------------------------


class StatsOut(BaseModel):
    """Statystyki sprzedaży zwracane przez `/api/v1/stats`."""

    orders_today: int
    orders_this_month: int
    revenue_today: float
    revenue_this_month: float
    total_orders: int


def stats_out(summary: StatsSummary) -> StatsOut:
    """Mapuje `StatsSummary` na schemat odpowiedzi API."""
    return StatsOut(
        orders_today=summary.orders_today,
        orders_this_month=summary.orders_this_month,
        revenue_today=summary.revenue_today,
        revenue_this_month=summary.revenue_this_month,
        total_orders=summary.total_orders,
    )


class HealthOut(BaseModel):
    """Status zdrowia zwracany przez `/api/v1/health`."""

    uptime: str
    last_sync: str
    database_ok: bool
    marketplace_connection_ok: bool


def health_out(health: HealthStatus) -> HealthOut:
    """Mapuje `HealthStatus` na schemat odpowiedzi API."""
    return HealthOut(
        uptime=health.uptime_human,
        last_sync=health.last_sync_human,
        database_ok=health.database_ok,
        marketplace_connection_ok=health.marketplace_connection_ok,
    )


class DashboardOut(BaseModel):
    """Podsumowanie zwracane przez `/api/v1/dashboard` (ekran Start)."""

    orders_today: int
    revenue_today: float
    orders_to_ship: int
    revenue_last_7_days: list[float]
    trend_percent: float | None
    last_sync_human: str
    marketplace_connection_ok: bool


def dashboard_out(summary: DashboardSummary, health: HealthStatus) -> DashboardOut:
    """Łączy `DashboardSummary` i `HealthStatus` w jedną odpowiedź API."""
    return DashboardOut(
        orders_today=summary.orders_today,
        revenue_today=summary.revenue_today,
        orders_to_ship=summary.orders_to_ship,
        revenue_last_7_days=list(summary.revenue_last_7_days),
        trend_percent=summary.trend_percent,
        last_sync_human=health.last_sync_human,
        marketplace_connection_ok=health.marketplace_connection_ok,
    )


class PushSubscriptionKeysIn(BaseModel):
    """Klucze kryptograficzne subskrypcji Web Push zwrócone przez przeglądarkę."""

    p256dh: str = Field(min_length=1)
    auth: str = Field(min_length=1)


class PushSubscriptionIn(BaseModel):
    """
    Ciało żądania `POST /api/v1/push/subscribe`.

    Kształt 1:1 z tym, co zwraca `PushSubscription.toJSON()` w
    przeglądarce (`endpoint` + `keys.p256dh` + `keys.auth`).
    """

    endpoint: str = Field(min_length=1)
    keys: PushSubscriptionKeysIn


class PushUnsubscribeIn(BaseModel):
    """Ciało żądania `DELETE /api/v1/push/subscribe`."""

    endpoint: str = Field(min_length=1)


class VapidPublicKeyOut(BaseModel):
    """Odpowiedź `GET /api/v1/push/vapid-public-key`."""

    public_key: str
    enabled: bool


class EventOut(BaseModel):
    """Zdarzenie systemowe zwracane przez `/api/v1/logs`."""

    event_type: str
    level: str
    created_at: UtcDatetime


def event_out(event: EventRecord) -> EventOut:
    """Mapuje `EventRecord` na schemat odpowiedzi API."""
    return EventOut(
        event_type=event.event_type, level=event.level, created_at=event.created_at
    )
