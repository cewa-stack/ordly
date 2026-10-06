"""
ORDLy Control Hub - co i kiedy ORDLY wysyła konsoli na ESP32.

Hub jest "głupim" ekranem: pokazuje, co dostanie, i odsyła potwierdzenie
przyciskiem OK. Cała decyzja, co jest zdarzeniem, kiedy ono znika i ile
dziś sprzedano, zapada tutaj. Tematy i format wiadomości: sekcja 7
specyfikacji Control Huba.

    ORDLY -> Hub:  ordly/events/new        nowe zdarzenie
                   ordly/events/resolved   zdarzenie zamknięte w ORDLY
                   ordly/events/snapshot   komplet aktywnych (po połączeniu Huba)
                   ordly/stats/today       statystyki dnia (retained)
                   ordly/system/status     stan ORDLY + godzina (retained)
    Hub -> ORDLY:  ordly/hub/ack           OK na Hubie
                   ordly/hub/status        Hub online/offline (retained, LWT)

Stan aktywnych zdarzeń leży w bazie (`hub_events`), nie w Hubie: Hub po
restarcie dostaje `snapshot` i jest w tym samym miejscu, co przed nim.
Zerwane połączenie z brokerem niczego nie gubi z tego samego powodu.
"""

from __future__ import annotations

from collections.abc import Callable, Collection
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.allegro_lokalnie_event import AllegroLokalnieEvent
from app.domain.entities.dispute_notice import DisputeNotice
from app.domain.entities.hub_event import (
    PRIORITY_AMBER,
    PRIORITY_BLUE,
    PRIORITY_RED,
    REASON_RECOVERED,
    REASON_STATUS_CHANGED,
    TYPE_DISPUTE,
    TYPE_MESSAGE,
    TYPE_NEW_ORDER,
    TYPE_RETURN,
    TYPE_SYSTEM_PROBLEM,
    TYPE_WHOLESALE_PARCEL,
    HubEvent,
    parse_event_id,
)
from app.domain.entities.olx_event import OlxEvent
from app.domain.entities.order import Order
from app.domain.entities.order_return import OrderReturn
from app.domain.entities.wholesale_parcel import WholesaleParcelNotice
from app.domain.fulfillment import is_cancelled_order
from app.domain.returns import ReturnStatusChange, return_requires_action
from app.repositories.sqlite_event_repository import SqliteEventRepository
from app.repositories.sqlite_hub_event_repository import SqliteHubEventRepository
from app.repositories.sqlite_order_repository import SqliteOrderRepository
from app.repositories.sqlite_return_repository import SqliteReturnRepository
from app.utils.time import local_midnight_utc, local_today, to_local, utc_now

TOPIC_EVENT_NEW = "ordly/events/new"
TOPIC_EVENT_RESOLVED = "ordly/events/resolved"
TOPIC_EVENT_SNAPSHOT = "ordly/events/snapshot"
TOPIC_STATS_TODAY = "ordly/stats/today"
TOPIC_SYSTEM_STATUS = "ordly/system/status"
TOPIC_HUB_ACK = "ordly/hub/ack"
TOPIC_HUB_STATUS = "ordly/hub/status"

#: Ile aktywnych zdarzeń najwyżej trafia do snapshotu. Hub ma mało RAM-u
#: (bufor MQTT 8 KB), a ekran i tak mieści kilka wierszy - liczbę
#: wszystkich pokazuje plakietka z pola `total`.
SNAPSHOT_LIMIT = 20
#: Długość opisu (produkty, tytuł ogłoszenia) - Hub i tak przytnie go do szerokości wiersza.
SUMMARY_MAX_CHARS = 60

#: Nazwy kanałów do treści problemu z systemem (klucz z SyncFailureTracker).
_CHANNEL_LABELS = {
    "allegro": "Allegro nie odpowiada",
    "poczta": "Poczta nie odpowiada",
}

#: Etapy realizacji, przy których zamówienie jest wciąż "nowe" dla Huba.
#: NULL mają zamówienia z Allegro Lokalnie (z maila nie znamy etapu).
_NEW_ORDER_FULFILLMENT = {None, "NEW"}


class HubPublisher(Protocol):
    """Wysyłka wiadomości do brokera MQTT (implementacja: `MqttHubBridge`)."""

    async def publish(self, topic: str, payload: dict[str, Any], retain: bool = False) -> bool:
        """Wysyła wiadomość. Zwraca False, gdy broker jest niedostępny."""
        ...


class HubEventsService:
    """Zamienia zdarzenia ORDLY na wiadomości dla Huba i obsługuje jego potwierdzenia."""

    def __init__(
        self,
        session_scope_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
        publisher: HubPublisher,
        last_sync_at: Callable[[], datetime | None] = lambda: None,
    ) -> None:
        """
        Args:
            session_scope_factory: Fabryka krótkich sesji bazy - serwis
                działa poza żądaniem HTTP (Event Bus, wiadomości MQTT).
            publisher: Wysyłka do brokera.
            last_sync_at: Czas ostatniej udanej synchronizacji zamówień
                (naiwny UTC) - do ekranu "Status systemu" na Hubie.
        """
        self._session_scope = session_scope_factory
        self._publisher = publisher
        self._last_sync_at = last_sync_at

    # ------------------------------------------------------------------
    # Zdarzenia ORDLY -> nowe wpisy na Hubie
    # ------------------------------------------------------------------

    async def on_order_created(self, order: Order) -> None:
        """Nowe zamówienie - czerwona dioda."""
        await self._open(
            source_key=_order_key(order.marketplace, order.external_id),
            type_=TYPE_NEW_ORDER,
            priority=PRIORITY_RED,
            data={
                "order_id": order.external_id,
                "marketplace": order.marketplace,
                "value": _money(order.total_amount),
                "buyer": order.buyer.login,
                "summary": _short(order.products_summary),
            },
        )

    async def on_order_closed(self, order: Order) -> None:
        """Zamówienie anulowane albo w pakowaniu - znika z Huba bez naciskania OK."""
        await self._resolve(
            _order_key(order.marketplace, order.external_id), REASON_STATUS_CHANGED
        )

    async def on_return_created(self, order_return: OrderReturn) -> None:
        """Nowy zwrot - pomarańczowa dioda."""
        await self._open(
            source_key=_return_key(order_return.marketplace, order_return.external_id),
            type_=TYPE_RETURN,
            priority=PRIORITY_AMBER,
            data={
                "order_id": order_return.order_external_id,
                "marketplace": order_return.marketplace,
                "value": _money(
                    sum(
                        (p.unit_price * p.quantity for p in order_return.products),
                        start=Decimal("0"),
                    )
                ),
                "buyer": order_return.buyer_login,
                "summary": _short(order_return.products_summary),
            },
        )

    async def on_return_status_changed(self, change: ReturnStatusChange) -> None:
        """Zamknięty zwrot znika z Huba."""
        if change.closes_return:
            await self._resolve(
                _return_key(change.marketplace, change.external_id), REASON_STATUS_CHANGED
            )

    async def on_dispute(self, notice: DisputeNotice) -> None:
        """Nowa dyskusja na Allegro - pomarańczowa dioda."""
        await self._open(
            source_key=f"dispute:{notice.issue_id}",
            type_=TYPE_DISPUTE,
            priority=PRIORITY_AMBER,
            data={
                "order_id": notice.order_external_id,
                "marketplace": "allegro",
                "buyer": notice.buyer_login,
                "summary": _short(notice.reason or notice.offer_name or ""),
            },
        )

    async def on_allegro_lokalnie(self, event: AllegroLokalnieEvent) -> None:
        """
        Allegro Lokalnie: wiadomość albo zwrot kupującego - pomarańczowa.

        Sprzedaż z kompletem danych przychodzi osobno jako `OrderCreated`
        (patrz event_subscriptions), a powiadomienia "ktoś obserwuje"
        czy "zmiana statusu" nie wymagają niczego od sprzedawcy.
        """
        type_ = {"new_message": TYPE_MESSAGE, "return": TYPE_RETURN}.get(event.event_type)
        if type_ is None:
            return
        await self._open(
            source_key=f"mail:{event.message_id}",
            type_=type_,
            priority=PRIORITY_AMBER,
            data={
                "marketplace": "allegro_lokalnie",
                "buyer": event.buyer_login or event.buyer_name,
                "summary": _short(event.listing_title or event.subject),
            },
        )

    async def on_olx(self, event: OlxEvent) -> None:
        """
        OLX: sprzedaż - czerwona, wiadomość i zwrot - pomarańczowa.

        Sprzedaż z OLX nie jest zamówieniem w ORDLY (mail nie podaje
        kwoty), więc nic jej nie zamknie samo - zostaje do potwierdzenia OK.
        """
        mapping = {
            "new_order": (TYPE_NEW_ORDER, PRIORITY_RED),
            "new_message": (TYPE_MESSAGE, PRIORITY_AMBER),
            "return": (TYPE_RETURN, PRIORITY_AMBER),
        }
        if event.event_type not in mapping:
            return
        type_, priority = mapping[event.event_type]
        await self._open(
            source_key=f"mail:{event.message_id}",
            type_=type_,
            priority=priority,
            data={
                "order_id": event.order_id,
                "marketplace": "olx",
                "value": None,
                "summary": _short(event.listing_title or event.subject),
            },
        )

    async def on_wholesale_parcel(self, notice: WholesaleParcelNotice) -> None:
        """
        Paczka od hurtowni nadana przez InPost ([FEAT-MAIL]) - pomarańczowa
        dioda (decyzja M3-a), tylko informacja. Zamknięcie = OK na Hubie;
        nic w ORDLY nie zamyka jej samo. Klucz per mail: ponowne pobranie
        tego samego maila nie da drugiego wpisu.
        """
        await self._open(
            source_key=f"parcel_mail:{notice.message_id}",
            type_=TYPE_WHOLESALE_PARCEL,
            priority=PRIORITY_AMBER,
            data={
                "carrier": "InPost",
                "tracking_number": notice.tracking_number,
                "wholesaler": notice.wholesaler_name,
                "summary": _short(f"{notice.wholesaler_name} · InPost {notice.tracking_number}"),
            },
        )

    async def sync_system_problems(self, alerted_channels: Collection[str]) -> None:
        """
        Problem z systemem = kanał, o którym poszedł już alert (druga
        nieudana synchronizacja z rzędu, `SyncFailureTracker`). Niebieska
        miga szybko, dopóki kanał nie odpowie albo ktoś nie naciśnie OK.
        """
        wanted = {f"system:{channel}" for channel in alerted_channels}
        for channel in sorted(alerted_channels):
            await self._open(
                source_key=f"system:{channel}",
                type_=TYPE_SYSTEM_PROBLEM,
                priority=PRIORITY_BLUE,
                data={"channel": channel, "summary": _CHANNEL_LABELS.get(channel, channel)},
                reopen=True,
            )
        async with self._session_scope() as session:
            unresolved = await SqliteHubEventRepository(session).get_active_by_source_prefix(
                "system:", include_acknowledged=True
            )
        for event in unresolved:
            if event.source_key not in wanted:
                # Kanał wrócił: koniec serii. Potwierdzony już problem
                # domykamy po cichu - Hub i tak go nie pokazuje - żeby
                # kolejna awaria otworzyła go od nowa.
                await self._resolve(
                    event.source_key, REASON_RECOVERED, include_acknowledged=True
                )

    async def reconcile(self) -> None:
        """
        Zamyka zdarzenia, których sprawa zmieniła się w ORDLY bez osobnego
        zdarzenia na Event Busie - np. zamówienie spakowane i nadane od razu
        (numer przesyłki bez etapu PROCESSING) albo zwrot zamknięty, zanim
        ORDLY zdążył zobaczyć pośredni status.
        """
        to_resolve: list[str] = []
        async with self._session_scope() as session:
            repository = SqliteHubEventRepository(session)
            orders = SqliteOrderRepository(session)
            returns = SqliteReturnRepository(session)
            for event in await repository.get_active_by_source_prefix("order:"):
                _, marketplace, external_id = event.source_key.split(":", 2)
                order = await orders.get_by_external_id(external_id)
                if (
                    order is not None
                    and order.marketplace == marketplace
                    and not _is_new(order)
                ):
                    to_resolve.append(event.source_key)
            for event in await repository.get_active_by_source_prefix("return:"):
                _, marketplace, external_id = event.source_key.split(":", 2)
                status = await returns.get_status(marketplace, external_id)
                if status is not None and not return_requires_action(status):
                    to_resolve.append(event.source_key)
        for source_key in to_resolve:
            await self._resolve(source_key, REASON_STATUS_CHANGED)

    # ------------------------------------------------------------------
    # Hub -> ORDLY
    # ------------------------------------------------------------------

    async def handle_ack(self, payload: dict[str, Any]) -> None:
        """
        OK na Hubie zamyka zdarzenie. Nieznany numer albo podwójne
        naciśnięcie nic nie robią - Hub sam już zdjął wpis z ekranu.
        """
        event_id = parse_event_id(payload.get("event_id"))
        if event_id is None:
            logger.warning("Hub: potwierdzenie bez poprawnego event_id: {}", payload)
            return
        async with self._session_scope() as session:
            acknowledged = await SqliteHubEventRepository(session).acknowledge(event_id)
            if acknowledged is None:
                logger.info("Hub: evt_{} już zamknięte albo nieznane - pomijam", event_id)
                return
            await SqliteEventRepository(session).record(
                event_type="HubEventAcknowledged",
                level="INFO",
                payload={
                    "event_id": acknowledged.event_id,
                    "source_key": acknowledged.source_key,
                },
            )
        logger.info(
            "Hub: potwierdzono {} ({})", acknowledged.event_id, acknowledged.source_key
        )

    async def handle_hub_status(self, payload: dict[str, Any]) -> None:
        """
        Hub ogłosił, że jest online - dostaje komplet aktywnych zdarzeń,
        statystyki i stan systemu. Tak samo po restarcie ORDLY (status
        Huba jest retained, więc przychodzi zaraz po połączeniu z brokerem).
        """
        if payload.get("online") is not True:
            logger.info("Hub: offline")
            return
        logger.info(
            "Hub: online (firmware {}, IP {})", payload.get("fw_version"), payload.get("ip")
        )
        await self.publish_snapshot()
        await self.publish_stats()
        await self.publish_system_status()

    # ------------------------------------------------------------------
    # Wiadomości okresowe i snapshot
    # ------------------------------------------------------------------

    async def publish_snapshot(self) -> None:
        """Wysyła komplet aktywnych zdarzeń - Hub zastępuje nim swoją listę."""
        async with self._session_scope() as session:
            repository = SqliteHubEventRepository(session)
            events = await repository.get_active(SNAPSHOT_LIMIT)
            total = await repository.count_active()
        await self._publisher.publish(
            TOPIC_EVENT_SNAPSHOT,
            {
                "events": [_event_payload(event) for event in events],
                "total": total,
                "ts": _local_iso(utc_now()),
            },
        )

    async def publish_stats(self) -> None:
        """
        Statystyki dnia - te same liczby, co ekran Start w aplikacji
        (polska doba, `sum_amount_since`). Porównanie z wczoraj jest do tej
        samej godziny, a nie z całym wczorajszym dniem: o 10:00 dzień
        zawsze przegrywałby z pełną wczorajszą dobą.
        """
        now = utc_now()
        today_start = local_midnight_utc(local_today())
        yesterday_start = local_midnight_utc(local_today() - timedelta(days=1))
        async with self._session_scope() as session:
            orders = SqliteOrderRepository(session)
            orders_today = await orders.count_since(today_start)
            revenue_today = await orders.sum_amount_since(today_start)
            # Wczoraj od północy do "teraz minus doba".
            revenue_yesterday_so_far = await orders.sum_amount_since(
                yesterday_start
            ) - await orders.sum_amount_since(now - timedelta(days=1))

        vs_yesterday_pct: int | None = None
        if revenue_yesterday_so_far > 0:
            vs_yesterday_pct = round(
                (revenue_today - revenue_yesterday_so_far) / revenue_yesterday_so_far * 100
            )
        await self._publisher.publish(
            TOPIC_STATS_TODAY,
            {
                "revenue": round(revenue_today, 2),
                "orders": orders_today,
                "avg_order": round(revenue_today / orders_today, 2) if orders_today else 0,
                "vs_yesterday_pct": vs_yesterday_pct,
                "ts": _local_iso(now),
            },
            retain=True,
        )

    async def publish_system_status(self) -> None:
        """
        Stan ORDLY dla ekranu "Status systemu" i godzina dla trybu nocnego.

        Hub nie łączy się z internetem (także z serwerami czasu) - zegar
        bierze z pola `ts` tej wiadomości, wysyłanej co minutę.
        """
        last_sync = self._last_sync_at()
        async with self._session_scope() as session:
            problems = await SqliteHubEventRepository(session).get_active_by_source_prefix(
                "system:"
            )
        await self._publisher.publish(
            TOPIC_SYSTEM_STATUS,
            {
                "ts": _local_iso(utc_now()),
                "last_sync_at": _local_iso(last_sync) if last_sync else None,
                "problems": [str(event.data.get("summary", "")) for event in problems],
            },
            retain=True,
        )

    async def run_periodic(self, alerted_channels: Collection[str]) -> None:
        """Jeden cykl joba co minutę: problemy z systemem, porządki, stan, statystyki."""
        await self.sync_system_problems(alerted_channels)
        await self.reconcile()
        await self.publish_system_status()
        await self.publish_stats()

    # ------------------------------------------------------------------

    async def _open(
        self,
        source_key: str,
        type_: str,
        priority: str,
        data: dict[str, Any],
        reopen: bool = False,
    ) -> None:
        async with self._session_scope() as session:
            repository = SqliteHubEventRepository(session)
            if reopen:
                event = await repository.reopen_or_open(source_key, type_, priority, data)
            else:
                event = await repository.open(source_key, type_, priority, data)
        if event is None:
            return
        logger.info("Hub: nowe zdarzenie {} ({})", event.event_id, source_key)
        await self._publisher.publish(TOPIC_EVENT_NEW, _event_payload(event))

    async def _resolve(
        self, source_key: str, reason: str, include_acknowledged: bool = False
    ) -> None:
        async with self._session_scope() as session:
            event = await SqliteHubEventRepository(session).resolve_by_source_key(
                source_key, reason, include_acknowledged=include_acknowledged
            )
        if event is None or event.acked_at is not None:
            return
        logger.info("Hub: zamknięte {} ({}, {})", event.event_id, source_key, reason)
        await self._publisher.publish(
            TOPIC_EVENT_RESOLVED, {"event_id": event.event_id, "reason": reason}
        )


def _order_key(marketplace: str, external_id: str) -> str:
    return f"order:{marketplace}:{external_id}"


def _return_key(marketplace: str, external_id: str) -> str:
    return f"return:{marketplace}:{external_id}"


def _is_new(order: Order) -> bool:
    """Czy zamówienie wciąż czeka, aż ktoś je zauważy (nikt go nie ruszył)."""
    if is_cancelled_order(order.status, order.fulfillment_status) or order.tracking_number:
        return False
    fulfillment = order.fulfillment_status.upper() if order.fulfillment_status else None
    return fulfillment in _NEW_ORDER_FULFILLMENT


def _money(value: Decimal | None) -> float | None:
    return float(round(value, 2)) if value is not None else None


def _short(text: str) -> str:
    text = " ".join(text.split())
    if len(text) <= SUMMARY_MAX_CHARS:
        return text
    return text[: SUMMARY_MAX_CHARS - 1].rstrip() + "…"


def _local_iso(value: datetime) -> str:
    """Naiwny UTC z bazy -> czas polski z przesunięciem, np. 2026-10-04T12:04:00+02:00."""
    return to_local(value).isoformat(timespec="seconds")


def _event_payload(event: HubEvent) -> dict[str, Any]:
    """Wiadomość `ordly/events/new` w formacie z sekcji 7 specyfikacji."""
    return {
        "id": event.event_id,
        "type": event.type,
        "priority": event.priority,
        "ts": _local_iso(event.created_at),
        "data": {key: value for key, value in event.data.items() if value is not None},
    }
