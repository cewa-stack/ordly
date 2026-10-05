"""
ORDLy Control Hub - ekran "Historia sprzedaży".

Hub nie trzyma historii: na każde naciśnięcie przycisku prosi o jeden
ekran (dzień + strona), a ORDLY odsyła gotowe wiersze, nagłówek dnia
z liczbą zamówień i kwotą oraz sąsiednie dni, w których coś się sprzedało.
Dzięki temu można cofać się dowolnie daleko przy kilku KB RAM-u w ESP32.

    Hub -> ORDLY:  ordly/hub/history/get  {date?: "RRRR-MM-DD", page?: 0}
    ORDLY -> Hub:  ordly/history/day      jeden ekran historii

Doba jest polska (`local_midnight_utc`), a suma i liczba zamówień liczą się
tak samo jak w Statystykach Huba i na ekranie Start: bez anulowanych
(status zamówienia CANCELLED). Anulowane są na liście z `cancelled: true`,
żeby było widać, że takie zamówienie było.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.order import Order
from app.repositories.sqlite_order_repository import SqliteOrderRepository
from app.services.hub_events_service import HubPublisher
from app.utils.time import local_midnight_utc, local_today, to_local

TOPIC_HISTORY_GET = "ordly/hub/history/get"
TOPIC_HISTORY_DAY = "ordly/history/day"

#: Tyle wierszy mieści się na jednym ekranie Huba (dwie linie na zamówienie).
HISTORY_PAGE_SIZE = 5
#: Długość opisu produktów - Hub i tak przytnie go do szerokości wiersza.
HISTORY_SUMMARY_MAX_CHARS = 48

_WEEKDAYS = ("pon.", "wt.", "śr.", "czw.", "pt", "sob.", "niedz.")
_CANCELLED = "CANCELLED"


class HubHistoryService:
    """Odpowiada Hubowi na prośby o historię sprzedaży, dzień po dniu."""

    def __init__(
        self,
        session_scope_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
        publisher: HubPublisher,
        today: Callable[[], date] = local_today,
    ) -> None:
        """
        Args:
            session_scope_factory: Fabryka krótkich sesji bazy.
            publisher: Wysyłka do brokera.
            today: Dzisiejsza data w Polsce (podmieniana w testach).
        """
        self._session_scope = session_scope_factory
        self._publisher = publisher
        self._today = today

    async def handle_request(self, payload: dict[str, Any]) -> None:
        """Prośba Huba o ekran historii - odpowiedź idzie na `ordly/history/day`."""
        await self._publisher.publish(TOPIC_HISTORY_DAY, await self.build_day(payload))

    async def build_day(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Jeden ekran historii.

        Brak daty, zła data albo data z przyszłości = dziś. Strona poza
        zakresem = ostatnia strona dnia (Hub mógł prosić o stronę, która
        zniknęła, bo np. zamówienie zostało usunięte).
        """
        today = self._today()
        day = _parse_day(payload.get("date"), today)
        page = payload.get("page")
        page = page if isinstance(page, int) and page >= 0 else 0

        start = local_midnight_utc(day)
        end = local_midnight_utc(day + timedelta(days=1))
        async with self._session_scope() as session:
            orders_repo = SqliteOrderRepository(session)
            orders = await orders_repo.get_between(start, end)
            previous = await orders_repo.latest_order_date_before(start)
            following = (
                await orders_repo.earliest_order_date_since(end) if day < today else None
            )

        sold = [order for order in orders if not _is_cancelled(order)]
        pages = max(1, -(-len(orders) // HISTORY_PAGE_SIZE))
        page = min(page, pages - 1)
        rows = orders[page * HISTORY_PAGE_SIZE : (page + 1) * HISTORY_PAGE_SIZE]
        logger.debug("Hub: historia {} strona {}/{}", day, page + 1, pages)
        return {
            "date": day.isoformat(),
            "label": _day_label(day, today),
            "orders_count": len(sold),
            "revenue": float(round(sum((o.total_amount for o in sold), Decimal("0")), 2)),
            "page": page,
            "pages": pages,
            "rows": [_row(order) for order in rows],
            "prev_date": to_local(previous).date().isoformat() if previous else None,
            "next_date": _next_day(day, following, today),
        }


def _parse_day(value: Any, today: date) -> date:
    if isinstance(value, str):
        try:
            day = date.fromisoformat(value)
        except ValueError:
            return today
        return min(day, today)
    return today


def _next_day(day: date, following: datetime | None, today: date) -> str | None:
    """
    Nowszy dzień ze sprzedażą. Gdy po tym dniu nic się nie sprzedało,
    a to nie jest dziś - dziś (Hub zawsze może wrócić do bieżącego dnia).
    """
    if day >= today:
        return None
    if following is not None:
        return to_local(following).date().isoformat()
    return today.isoformat()


def _day_label(day: date, today: date) -> str:
    """'Dziś, pon. 5.10', 'Wczoraj, niedz. 4.10', 'pt 2.10' (rok tylko, gdy inny)."""
    short = f"{_WEEKDAYS[day.weekday()]} {day.day}.{day.month:02d}"
    if day.year != today.year:
        short += f".{day.year}"
    if day == today:
        return f"Dziś, {short}"
    if day == today - timedelta(days=1):
        return f"Wczoraj, {short}"
    return short


def _is_cancelled(order: Order) -> bool:
    # Ta sama reguła co `sum_amount_since` - suma dnia zgadza się ze Statystykami.
    return order.status.upper() == _CANCELLED


def _row(order: Order) -> dict[str, Any]:
    return {
        "time": to_local(order.order_date).strftime("%H:%M"),
        "marketplace": order.marketplace,
        "summary": _summary(order),
        "value": float(round(order.total_amount, 2)),
        "buyer": order.buyer.login,
        "order_id": order.external_id,
        "cancelled": _is_cancelled(order),
    }


def _summary(order: Order) -> str:
    """Pierwszy produkt z ilością i '+N', gdy w zamówieniu jest więcej pozycji."""
    if not order.products:
        return "brak danych"
    first = order.products[0]
    text = " ".join(first.name.split())
    if first.quantity > 1:
        text += f" x{first.quantity}"
    more = f" +{len(order.products) - 1}" if len(order.products) > 1 else ""
    limit = HISTORY_SUMMARY_MAX_CHARS - len(more)
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text + more
