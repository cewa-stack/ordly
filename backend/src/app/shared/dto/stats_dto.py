"""DTO wyników agregacji statystyk sprzedaży i synchronizacji."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.entities.order import Order
    from app.domain.entities.order_return import OrderReturn


@dataclass(frozen=True, slots=True)
class StatsSummary:
    """Podsumowanie statystyk zwracane przez komendę /stats."""

    orders_today: int
    orders_this_month: int
    revenue_today: float
    revenue_this_month: float
    total_orders: int


@dataclass(frozen=True, slots=True)
class SyncResult:
    """
    Wynik operacji synchronizacji zamówień.

    `new_orders` zawiera pełne encje nowo zapisanych zamówień - służy
    do opublikowania zdarzeń OrderCreated PO zatwierdzeniu transakcji
    (zob. SyncOrdersService.publish_sync_events). Analogicznie
    `cancelled_orders` (zamówienia, których status zmienił się na
    anulowane) oraz `new_returns` (nowo wykryte zwroty klientów).
    """

    new_orders_count: int
    checked_orders_count: int
    new_orders: tuple[Order, ...] = field(default=())
    cancelled_orders: tuple[Order, ...] = field(default=())
    new_returns: tuple[OrderReturn, ...] = field(default=())
    packing_started_orders: tuple[Order, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class HealthStatus:
    """Wynik sprawdzenia stanu zdrowia aplikacji dla komendy /health."""

    uptime_human: str
    last_sync_human: str
    database_ok: bool
    marketplace_connection_ok: bool
