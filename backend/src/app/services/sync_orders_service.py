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

# Ile zamówień spoza okna listy (`get_orders` zwraca tylko najnowsze)
# odświeżamy pojedynczo w jednym cyklu. W zdrowym sklepie wszystkie
# otwarte zamówienia mieszczą się w oknie i ta pętla nie robi ani jednego
# zapytania - limit chroni tylko przed zalaniem Allegro, gdyby w bazie
# zalegało dużo starych, nigdy niepotwierdzonych zamówień. Kandydatów
# pobieramy z zapasem, bo część z nich jest w oknie i odpada.
_MAX_OUT_OF_WINDOW_REFRESHES = 25
_REFRESH_CANDIDATES_LIMIT = 200
_HTTP_NOT_FOUND = 404


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

        fetched_ids = {order.external_id for order in orders}
        for refreshed, change in await self._refresh_orders_outside_window(fetched_ids):
            if change.cancelled:
                cancelled_orders.append(refreshed)
            if change.packing_started:
                packing_started_orders.append(refreshed)

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

        return _ExistingOrderChange(cancelled=cancelled, packing_started=packing_started)

    async def _refresh_orders_outside_window(
        self, fetched_ids: set[str]
    ) -> list[tuple[Order, _ExistingOrderChange]]:
        """
        Potwierdza u źródła stan otwartych zamówień, których nie było
        w pobranej liście.

        `get_orders` zwraca tylko najnowsze checkout-formy. Zamówienie,
        które z nich wypadło, zostawało w bazie z ostatnim widzianym etapem
        (NEW albo NULL) na zawsze - aplikacja liczyła je do "czeka na
        spakowanie" i przypominała o nim miesiącami, choć na Allegro było
        dawno obsłużone. Tu każde takie zamówienie jest pobierane
        pojedynczo i przechodzi przez tę samą ścieżkę porównania co
        zamówienia z listy.

        Błąd Allegro dla jednego zamówienia nie zmienia niczego w bazie
        (dane lokalne zostają). 404 = Allegro nie udostępnia już tego
        zamówienia - pomijamy je; każdy inny błąd (sieć, 5xx, limit
        zapytań) przerywa pętlę do następnego cyklu, żeby nie dobijać
        niedostępnego API.

        Zdarzenia (anulowanie, rozpoczęcie pakowania) wychodzą tylko dla
        zamówień, których etap był znany (nie NULL) - korekta starego
        rekordu bez etapu to nadrabianie historii, a nie zmiana "na żywo",
        i nie może wysłać klientowi SMS-a o pakowaniu zamówienia sprzed
        miesięcy.
        """
        candidates = await self._order_repository.get_open_for_refresh(
            self._plugin.marketplace_code, _REFRESH_CANDIDATES_LIMIT
        )
        stale = [order for order in candidates if order.external_id not in fetched_ids]
        if len(stale) > _MAX_OUT_OF_WINDOW_REFRESHES:
            # Rotacja co minutę: gdy kandydatów jest więcej niż limit,
            # każdy cykl zaczyna od innego miejsca, więc żadne zamówienie
            # nie czeka w nieskończoność za tymi samymi 25.
            start = (
                int(utc_now().timestamp()) // 60 * _MAX_OUT_OF_WINDOW_REFRESHES
            ) % len(stale)
            stale = stale[start:] + stale[:start]
            logger.info(
                "Zamówień do potwierdzenia spoza okna: {} - w tym cyklu {}",
                len(stale),
                _MAX_OUT_OF_WINDOW_REFRESHES,
            )

        refreshed: list[tuple[Order, _ExistingOrderChange]] = []
        for stored in stale[:_MAX_OUT_OF_WINDOW_REFRESHES]:
            try:
                fresh = await self._plugin.get_order(stored.external_id)
            except AllegroApiError as exc:
                if exc.status_code == _HTTP_NOT_FOUND:
                    logger.debug(
                        "Zamówienie {} niedostępne w Allegro (404) - zostaje bez zmian",
                        stored.external_id,
                    )
                    continue
                logger.warning(
                    "Odświeżanie zamówień spoza okna przerwane - Allegro: {}", exc
                )
                break

            change = await self._sync_existing_order_status(fresh)
            if stored.fulfillment_status is None:
                change = _ExistingOrderChange()
            refreshed.append((fresh, change))

        return refreshed

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
            await self._event_bus.publish(OrderCreated(occurred_at=utc_now(), order=order))

        for order in result.cancelled_orders:
            await self._event_bus.publish(OrderCancelled(occurred_at=utc_now(), order=order))

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

    async def get_recent_orders(self, limit: int, offset: int = 0) -> list[Order]:
        """Zwraca ostatnie zamówienia (delegacja do repozytorium, użyta przez /orders)."""
        return await self._order_repository.get_recent(limit, offset)

    async def get_order_by_external_id(self, external_id: str) -> Order:
        """Zwraca zamówienie po numerze lub rzuca OrderNotFoundError."""
        order = await self._order_repository.get_by_external_id(external_id)
        if order is None:
            raise OrderNotFoundError(external_id)
        return order

    async def set_fulfillment_status(self, external_id: str, status: str) -> Order:
        """
        Ustawia status realizacji na marketplace, a potem u siebie.

        Kolejnosc jest istotna: najpierw zapis na marketplace, dopiero
        potem lokalnie. Odwrotnie aplikacja pokazywalaby "wysłane" przy
        zamowieniu, ktorego kupujacy nadal widzi jako nieobsluzone.

        Raises:
            OrderNotFoundError: Gdy zamówienia nie ma w bazie.
            MarketplaceUnavailableError: Gdy marketplace odrzuci zapis.
        """
        order = await self.get_order_by_external_id(external_id)
        try:
            await self._plugin.set_fulfillment_status(external_id, status)
        except AllegroApiError as exc:
            logger.warning(
                "Marketplace odrzucił zmianę statusu realizacji {} na {}: {}",
                external_id,
                status,
                exc,
            )
            raise MarketplaceUnavailableError(str(exc)) from exc

        await self._order_repository.update_fulfillment_status(
            order.marketplace, external_id, status
        )
        return await self.get_order_by_external_id(external_id)
