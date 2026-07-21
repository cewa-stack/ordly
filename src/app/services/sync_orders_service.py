"""
Serwis synchronizacji zamówień - centralna logika biznesowa projektu.

Ta klasa nie wie nic o APScheduler ani komendzie Telegram /sync -
oba te miejsca jedynie ją wywołują.

WAŻNE - kolejność transakcji i zdarzeń:
sync_new_orders() wykonuje wyłącznie pracę na bazie danych i zwraca
listę nowych zamówień w SyncResult. Zdarzenia OrderCreated/SyncFinished
publikuje dopiero publish_sync_events(), wywoływane przez caller PO
zatwierdzeniu transakcji. Subskrybenci tych zdarzeń otwierają własne
sesje i piszą do tej samej bazy SQLite - publikacja wewnątrz otwartej
transakcji kończyłaby się blokadą zapisu (database is locked) oraz
aktualizacją niewidocznych jeszcze wierszy.
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from app.core.event_bus.bus import EventBus
from app.core.event_bus.events import (
    OrderCancelled,
    OrderCreated,
    OrderPackingStarted,
    OrderReturnCreated,
    SyncFinished,
    SyncStarted,
)
from app.domain.entities.order import Order
from app.domain.entities.order_return import OrderReturn
from app.domain.exceptions.domain_exceptions import (
    DuplicateOrderError,
    DuplicateReturnError,
    MarketplaceUnavailableError,
    OrderNotFoundError,
)
from app.domain.fulfillment import is_packing_started
from app.domain.interfaces.marketplace_plugin import MarketplacePlugin
from app.domain.interfaces.order_repository import OrderRepository
from app.domain.interfaces.return_repository import ReturnRepository
from app.infrastructure.plugins.allegro.exceptions import AllegroApiError
from app.shared.dto.stats_dto import SyncResult
from app.utils.time import utc_now

_CANCELLED_STATUS = "CANCELLED"


@dataclass(frozen=True, slots=True)
class _ExistingOrderChange:
    """Wynik porównania znanego zamówienia ze stanem zwróconym przez marketplace."""

    cancelled: bool = False
    packing_started: bool = False


class SyncOrdersService:
    """Wykrywa nowe zamówienia u marketplace i zapisuje je, emitując zdarzenia."""

    def __init__(
        self,
        plugin: MarketplacePlugin,
        order_repository: OrderRepository,
        event_bus: EventBus,
        return_repository: ReturnRepository | None = None,
    ) -> None:
        """
        Args:
            plugin: Aktywny plugin marketplace (np. AllegroPlugin).
            order_repository: Repozytorium dostępu do zamówień.
            event_bus: Magistrala zdarzeń do publikacji OrderCreated itd.
            return_repository: Repozytorium zwrotów klientów. Gdy None,
                synchronizacja zwrotów jest pomijana.
        """
        self._plugin = plugin
        self._order_repository = order_repository
        self._event_bus = event_bus
        self._return_repository = return_repository

    async def sync_new_orders(self) -> SyncResult:
        """
        Pobiera zamówienia z marketplace i zapisuje te, które są nowe.

        Dla zamówień już znanych porównuje status z zapisanym w bazie -
        zmianę utrwala, a przejście na status anulowany zgłasza
        w `cancelled_orders`. Dodatkowo pobiera zwroty klientów
        i zapisuje nowe w `new_returns`.

        Returns:
            Podsumowanie synchronizacji wraz z listami nowych zamówień,
            anulowanych zamówień i nowych zwrotów - po zatwierdzeniu
            transakcji przekaż je do publish_sync_events().

        Raises:
            MarketplaceUnavailableError: Gdy marketplace API jest niedostępne.
        """
        await self._event_bus.publish(SyncStarted(occurred_at=utc_now()))

        try:
            orders = await self._plugin.get_orders()
        except AllegroApiError as exc:
            logger.error("Synchronizacja przerwana - Allegro API niedostępne: {}", exc)
            raise MarketplaceUnavailableError(str(exc)) from exc

        new_orders: list[Order] = []
        cancelled_orders: list[Order] = []
        packing_started_orders: list[Order] = []
        for order in orders:
            already_exists = await self._order_repository.exists(
                order.marketplace, order.external_id
            )
            if already_exists:
                change = await self._sync_existing_order_status(order)
                if change.cancelled:
                    cancelled_orders.append(order)
                if change.packing_started:
                    packing_started_orders.append(order)
                continue

            try:
                await self._order_repository.save(order)
            except DuplicateOrderError:
                logger.debug(
                    "Zamówienie {} zapisane równolegle przez inną synchronizację - pomijam",
                    order.external_id,
                )
                continue

            new_orders.append(order)
            logger.info("Zapisano nowe zamówienie {}", order.external_id)

        new_returns = await self._sync_customer_returns()

        return SyncResult(
            new_orders_count=len(new_orders),
            checked_orders_count=len(orders),
            new_orders=tuple(new_orders),
            cancelled_orders=tuple(cancelled_orders),
            new_returns=tuple(new_returns),
            packing_started_orders=tuple(packing_started_orders),
        )

    async def _sync_existing_order_status(self, order: Order) -> _ExistingOrderChange:
        """
        Porównuje znane zamówienie ze stanem z marketplace i utrwala zmiany.

        Śledzi dwa niezależne wymiary: status płatności (`status`,
        wykrywa anulowanie) oraz etap realizacji (`fulfillment_status`,
        wykrywa rozpoczęcie pakowania). Oba są utrwalane osobno.

        Returns:
            Flagi mówiące, czy zamówienie właśnie zostało anulowane
            oraz czy właśnie weszło w etap pakowania.
        """
        stored = await self._order_repository.get_by_external_id(order.external_id)
        if stored is None:
            return _ExistingOrderChange()

        cancelled = False
        if stored.status != order.status:
            await self._order_repository.update_status(
                order.marketplace, order.external_id, order.status
            )
            logger.info(
                "Zamówienie {} zmieniło status: {} -> {}",
                order.external_id,
                stored.status,
                order.status,
            )
            cancelled = (
                order.status.upper() == _CANCELLED_STATUS
                and stored.status.upper() != _CANCELLED_STATUS
            )

        packing_started = False
        if stored.fulfillment_status != order.fulfillment_status:
            await self._order_repository.update_fulfillment_status(
                order.marketplace, order.external_id, order.fulfillment_status
            )
            logger.info(
                "Zamówienie {} zmieniło etap realizacji: {} -> {}",
                order.external_id,
                stored.fulfillment_status,
                order.fulfillment_status,
            )
            packing_started = is_packing_started(
                stored.fulfillment_status, order.fulfillment_status
            )

        return _ExistingOrderChange(
            cancelled=cancelled, packing_started=packing_started
        )

    async def _sync_customer_returns(self) -> list[OrderReturn]:
        """
        Pobiera zwroty klientów z marketplace i zapisuje nowe.

        Błąd pobierania zwrotów NIE przerywa całej synchronizacji -
        zamówienia są ważniejsze, a zwroty zostaną pobrane przy
        następnym cyklu (zasada odporności projektu).
        """
        if self._return_repository is None:
            return []

        try:
            returns = await self._plugin.get_customer_returns()
        except AllegroApiError as exc:
            logger.warning(
                "Nie udało się pobrać zwrotów klientów - pominięto w tym cyklu: {}",
                exc,
            )
            return []

        new_returns: list[OrderReturn] = []
        for order_return in returns:
            already_exists = await self._return_repository.exists(
                order_return.marketplace, order_return.external_id
            )
            if already_exists:
                continue

            try:
                await self._return_repository.save(order_return)
            except DuplicateReturnError:
                logger.debug(
                    "Zwrot {} zapisany równolegle przez inną synchronizację - pomijam",
                    order_return.external_id,
                )
                continue

            new_returns.append(order_return)
            logger.info(
                "Zapisano nowy zwrot {} dla zamówienia {}",
                order_return.external_id,
                order_return.order_external_id,
            )

        return new_returns

    async def publish_sync_events(self, result: SyncResult) -> None:
        """
        Publikuje zdarzenia OrderCreated, OrderCancelled, OrderReturnCreated
        i SyncFinished dla zakończonej synchronizacji.

        Musi być wywołane PO zamknięciu (commit) sesji bazy danych,
        w której działało sync_new_orders() - subskrybenci zdarzeń piszą
        do bazy we własnych sesjach i muszą widzieć zatwierdzone wiersze.
        """
        for order in result.new_orders:
            await self._event_bus.publish(
                OrderCreated(occurred_at=utc_now(), order=order)
            )

        for order in result.cancelled_orders:
            await self._event_bus.publish(
                OrderCancelled(occurred_at=utc_now(), order=order)
            )

        for order in result.packing_started_orders:
            await self._event_bus.publish(
                OrderPackingStarted(occurred_at=utc_now(), order=order)
            )

        for order_return in result.new_returns:
            await self._event_bus.publish(
                OrderReturnCreated(occurred_at=utc_now(), order_return=order_return)
            )

        await self._event_bus.publish(
            SyncFinished(
                occurred_at=utc_now(),
                new_orders_count=result.new_orders_count,
                checked_orders_count=result.checked_orders_count,
            )
        )

    async def get_recent_orders(self, limit: int) -> list[Order]:
        """Zwraca ostatnie zamówienia (delegacja do repozytorium, użyta przez /orders)."""
        return await self._order_repository.get_recent(limit)

    async def get_order_by_external_id(self, external_id: str) -> Order:
        """Zwraca zamówienie po numerze lub rzuca OrderNotFoundError."""
        order = await self._order_repository.get_by_external_id(external_id)
        if order is None:
            raise OrderNotFoundError(external_id)
        return order
