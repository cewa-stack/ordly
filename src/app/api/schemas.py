"""
Schematy Pydantic dla TOOM API (aplikacja mobilna TOOM Mobile).

Zasada: schematy tylko opisują kształt JSON i mapują encje domenowe na
odpowiedź HTTP (funkcje `*_out`) - żadnej logiki biznesowej. Logika żyje
wyłącznie w serwisach (`app/services/`), tak jak dla bota Telegram.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.inventory_movement import InventoryMovement
from app.domain.entities.order import Order
from app.domain.entities.shipment import Shipment
from app.repositories.sqlite_event_repository import EventRecord
from app.services.dashboard_service import DashboardSummary
from app.shared.dto.inventory_dto import InventoryReport, ItemForecast
from app.shared.dto.stats_dto import HealthStatus, StatsSummary, SyncResult

StockStatus = Literal["ok", "warning", "critical"]


# --------------------------------------------------------------------------
# Zamówienia
# --------------------------------------------------------------------------


class OrderProductOut(BaseModel):
    """Pojedyncza pozycja (produkt) w zamówieniu."""

    external_id: str
    name: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal


class OrderOut(BaseModel):
    """Zamówienie zwracane przez `/api/v1/orders`."""

    external_id: str
    marketplace: str
    buyer_login: str
    total_amount: Decimal
    currency: str
    status: str
    fulfillment_status: str | None
    order_date: datetime
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
    updated_at: datetime | None


def shipment_out(shipment: Shipment) -> ShipmentOut:
    """Mapuje encję domenową `Shipment` na schemat odpowiedzi API."""
    return ShipmentOut(
        order_external_id=shipment.order_external_id,
        carrier=shipment.carrier,
        tracking_number=shipment.tracking_number,
        status=shipment.status,
        updated_at=shipment.updated_at,
    )


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
# Magazyn
# --------------------------------------------------------------------------


def _stock_status(item: InventoryItem) -> StockStatus:
    """Odwzorowuje `status_emoji` z bota na status semantyczny dla apki."""
    if item.stock == 0 or item.is_low_stock:
        return "critical"
    if item.min_stock > 0 and item.stock <= 2 * item.min_stock:
        return "warning"
    return "ok"


class StockItemOut(BaseModel):
    """Produkt magazynowy zwracany przez `/api/v1/stock`."""

    sku: str
    name: str
    stock: int
    min_stock: int
    max_stock: int | None
    ean: str | None
    category: str | None
    location: str | None
    purchase_cost: Decimal | None
    sale_price: Decimal | None
    stock_value: Decimal
    is_low_stock: bool
    status: StockStatus


def stock_item_out(item: InventoryItem) -> StockItemOut:
    """Mapuje encję domenową `InventoryItem` na schemat odpowiedzi API."""
    return StockItemOut(
        sku=item.sku,
        name=item.name,
        stock=item.stock,
        min_stock=item.min_stock,
        max_stock=item.max_stock,
        ean=item.ean,
        category=item.category,
        location=item.location,
        purchase_cost=item.purchase_cost,
        sale_price=item.sale_price,
        stock_value=item.stock_value,
        is_low_stock=item.is_low_stock,
        status=_stock_status(item),
    )


class StockCreateIn(BaseModel):
    """Ciało żądania `POST /api/v1/stock` (nowy produkt magazynowy)."""

    sku: str = Field(min_length=1)
    name: str = Field(min_length=1)
    min_stock: int = Field(default=0, ge=0)


class StockAdjustIn(BaseModel):
    """Ciało żądania `POST /api/v1/stock/{sku}/adjust`."""

    op: Literal["set", "add", "remove", "min"]
    quantity: int = Field(ge=0)
    reason: str | None = None


class StockMovementOut(BaseModel):
    """Wpis historii magazynowej zwracany przez `/api/v1/stock/{sku}/history`."""

    item_sku: str
    item_name: str
    change: int
    stock_after: int
    reason: str
    source: str
    reference: str | None
    occurred_at: datetime


def stock_movement_out(movement: InventoryMovement) -> StockMovementOut:
    """Mapuje encję domenową `InventoryMovement` na schemat odpowiedzi API."""
    return StockMovementOut(
        item_sku=movement.item_sku,
        item_name=movement.item_name,
        change=movement.change,
        stock_after=movement.stock_after,
        reason=movement.reason,
        source=movement.source,
        reference=movement.reference,
        occurred_at=movement.occurred_at,
    )


class ItemForecastOut(BaseModel):
    """Prognoza wyczerpania zapasów dla jednego produktu."""

    sku: str
    name: str
    stock: int
    avg_daily_sales: float
    days_left: int


def item_forecast_out(forecast: ItemForecast) -> ItemForecastOut:
    """Mapuje `ItemForecast` na schemat odpowiedzi API."""
    return ItemForecastOut(
        sku=forecast.sku,
        name=forecast.name,
        stock=forecast.stock,
        avg_daily_sales=forecast.avg_daily_sales,
        days_left=forecast.days_left,
    )


class StockReportOut(BaseModel):
    """Raport magazynowy zwracany przez `/api/v1/stock/report`."""

    total_items: int
    total_stock_value: Decimal
    low_stock_items: list[StockItemOut]
    items_without_sales: list[StockItemOut]
    forecasts: list[ItemForecastOut]
    recent_movements: list[StockMovementOut]


def stock_report_out(report: InventoryReport) -> StockReportOut:
    """Mapuje `InventoryReport` na schemat odpowiedzi API."""
    return StockReportOut(
        total_items=report.total_items,
        total_stock_value=report.total_stock_value,
        low_stock_items=[stock_item_out(i) for i in report.low_stock_items],
        items_without_sales=[stock_item_out(i) for i in report.items_without_sales],
        forecasts=[item_forecast_out(f) for f in report.forecasts],
        recent_movements=[stock_movement_out(m) for m in report.recent_movements],
    )


class StockLinkIn(BaseModel):
    """Ciało żądania `POST /api/v1/stock/links` (mapowanie oferty na SKU)."""

    marketplace: str = Field(default="allegro")
    external_product_id: str = Field(min_length=1)
    sku: str = Field(min_length=1)
    quantity: int = Field(default=1, ge=1)


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
    low_stock_count: int
    revenue_last_7_days: list[float]
    trend_percent: float | None
    last_sync_human: str
    marketplace_connection_ok: bool


def dashboard_out(
    summary: DashboardSummary, health: HealthStatus
) -> DashboardOut:
    """Łączy `DashboardSummary` i `HealthStatus` w jedną odpowiedź API."""
    return DashboardOut(
        orders_today=summary.orders_today,
        revenue_today=summary.revenue_today,
        orders_to_ship=summary.orders_to_ship,
        low_stock_count=summary.low_stock_count,
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
    created_at: datetime


def event_out(event: EventRecord) -> EventOut:
    """Mapuje `EventRecord` na schemat odpowiedzi API."""
    return EventOut(
        event_type=event.event_type, level=event.level, created_at=event.created_at
    )
