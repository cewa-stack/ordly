"""
Implementacja Notifier wysyłająca powiadomienia przez Web Push (RFC 8030)
do ORDLY Mobile uruchomionego jako PWA (drugi kanał obok Telegrama,
przeznaczony głównie na iPhone'a, gdzie natywny push wymaga płatnego
konta Apple Developer).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Literal

from loguru import logger
from pywebpush import WebPushException, webpush
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.allegro_lokalnie_event import AllegroLokalnieEvent
from app.domain.entities.dispute_notice import DisputeNotice
from app.domain.entities.olx_event import OlxEvent
from app.domain.entities.order import Order
from app.domain.entities.order_return import OrderReturn
from app.domain.entities.push_subscription import PushSubscription
from app.domain.interfaces.notifier import Notifier
from app.infrastructure.webpush import push_payload
from app.infrastructure.webpush.order_batcher import OrderPushBatcher
from app.infrastructure.webpush.push_payload import PushPayload
from app.repositories.sqlite_push_subscription_repository import (
    SqlitePushSubscriptionRepository,
)
from app.services.attention_service import AttentionCounts
from app.shared.dto.reminder_dto import ShippingReminderData
from app.utils.time import local_now, to_local

_GONE_STATUS_CODES = (404, 410)

_SendOutcome = Literal["delivered", "expired", "failed"]


@dataclass(frozen=True, slots=True)
class PushDeliveryReport:
    """
    Wynik jednej wysyłki do wszystkich zapisanych subskrypcji.

    `delivered` liczy urządzenia, których serwer push (Apple/Google)
    przyjął powiadomienie - dalej backend nie widzi. `expired` to
    subskrypcje odrzucone jako martwe (404/410) i przy okazji usunięte.
    """

    subscriptions: int
    delivered: int
    expired: int
    failed: int


class WebPushNotifier(Notifier):
    """
    Rozgłasza powiadomienia biznesowe do wszystkich zapisanych subskrypcji
    Web Push.

    Brak zapisanych subskrypcji (nikt jeszcze nie włączył powiadomień w
    PWA) jest traktowany jako cichy sukces - to nie błąd, tylko stan
    "jeszcze nie skonfigurowano tego kanału". Wysyłka HTTP (`pywebpush`,
    biblioteka `requests`, synchroniczna) jest odsunięta do wątku
    (`asyncio.to_thread`), żeby nie blokować pętli zdarzeń asyncio.
    """

    def __init__(
        self,
        session_scope_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
        vapid_private_key: str,
        vapid_claim_email: str,
        attention_counter: Callable[[], Awaitable[AttentionCounts]] | None = None,
    ) -> None:
        """
        Args:
            session_scope_factory: `Container.session_scope` - Notifier
                jest tworzony bez sesji (tak jak TelegramNotifier), więc
                sam otwiera sobie krótkotrwałą sesję na czas jednej wysyłki.
            vapid_private_key: Klucz prywatny VAPID (base64url, format RAW).
            vapid_claim_email: Adres z prefiksem `mailto:` wymagany przez
                specyfikację VAPID jako identyfikator nadawcy.
            attention_counter: Liczy "Wymaga uwagi" z ekranu Start. Z tego
                powstaje plakietka na ikonie przy KAŻDYM powiadomieniu
                i poranny raport. `None` = plakietka bez zmian (testy).
        """
        self._attention_counter = attention_counter
        self._session_scope_factory = session_scope_factory
        self._vapid_private_key = vapid_private_key
        self._vapid_claims = {"sub": vapid_claim_email}
        self._batcher = OrderPushBatcher()

    async def notify_new_order(self, order: Order) -> None:
        """
        Nowe zamówienie - katalog powiadomień, pozycja „Nowe zamówienie".

        Przy serii zamówień (3 w 15 minut) `OrderPushBatcher` przełącza
        wysyłkę na jedno powiadomienie zbiorcze - patrz sekcja 04
        koncepcji push.
        """
        decision = self._batcher.accept(order)

        if decision.single is not None:
            await self._send(
                push_payload.new_order(
                    marketplace=order.marketplace,
                    amount=order.total_amount,
                    currency=order.currency,
                    products=[(p.quantity, p.name) for p in order.products],
                    external_id=order.external_id,
                )
            )
            return

        await self._notify_many_new_orders(list(decision.collective))

    async def _notify_many_new_orders(self, orders: list[Order]) -> None:
        """Buduje i wysyła zbiorcze powiadomienie o serii zamówień."""
        if not orders:
            return
        per_channel: dict[str, int] = {}
        total = sum((order.total_amount for order in orders), start=Decimal("0"))
        for order in orders:
            per_channel[order.marketplace] = per_channel.get(order.marketplace, 0) + 1
        await self._send(
            push_payload.many_new_orders(
                count=len(orders),
                per_channel=per_channel,
                total_amount=total,
                currency=orders[0].currency,
            )
        )

    async def notify_order_cancelled(self, order: Order) -> None:
        """
        Anulowane zamówienie - katalog, pozycja „Zamówienie anulowane”.

        Treść była dotąd budowana tutaj, poza katalogiem, i pokazywała login
        kupującego na ekranie blokady. Zostaje CICHE: anulowanie niczego od
        sprzedawcy nie wymaga.
        """
        await self._send(
            push_payload.order_cancelled(
                marketplace=order.marketplace,
                amount=order.total_amount,
                currency=order.currency,
                products=[(p.quantity, p.name) for p in order.products],
                external_id=order.external_id,
            )
        )

    async def notify_order_return(self, order_return: OrderReturn) -> None:
        """Nowy zwrot do decyzji - katalog, pozycja „Nowy zwrot"."""
        await self._send(
            push_payload.new_return(
                external_id=order_return.external_id,
                products_summary=order_return.products_summary,
                reason=order_return.status,
            )
        )

    async def notify_shipping_reminder(self, data: ShippingReminderData) -> None:
        """
        Wieczorne przypomnienie (20:00) - na telefon NIE wychodzi.

        Zastąpił je poranny raport o 9:00 (`send_morning_brief`), który mówi
        o paczkach, dyskusjach i zwrotach naraz. Telegram dostaje swoje
        przypomnienie o 20:00 bez zmian - to zdarzenie obsługuje dalej.
        """
        return

    async def send_morning_brief(self) -> PushDeliveryReport | None:
        """
        Poranny raport o 9:00 - tylko push, wołany z własnego zadania.

        `None`, gdy nic nie czeka albo nie da się policzyć stanu: pusty
        raport o 9:00 byłby hałasem.
        """
        if self._attention_counter is None:
            return None
        counts = await self._attention_counter()
        payload = push_payload.morning_brief(
            pending_count=counts.pending,
            oldest_local=(
                to_local(counts.oldest_pending_utc).replace(tzinfo=None)
                if counts.oldest_pending_utc is not None
                else None
            ),
            now_local=local_now().replace(tzinfo=None),
            open_issues=counts.open_issues or 0,
            open_returns=counts.open_returns,
        )
        if payload is None:
            return None
        return await self._send(payload, counts=counts)

    async def notify_active_orders(self, orders: list[Order]) -> None:
        """
        Lista aktualnych zamówień po nocnym czyszczeniu czatu (02:00).

        To zdarzenie obsługuje bota Telegram i wypada w środku godzin
        ciszy - do telefonu nie idzie nic, żeby nie budzić użytkownika
        podsumowaniem, które i tak poczeka do rana.
        """
        return

    async def notify_allegro_lokalnie(self, event: AllegroLokalnieEvent) -> None:
        """
        Zdarzenie z Allegro Lokalnie - katalog, pozycja „Allegro Lokalnie".

        Treść budujemy z katalogu, a NIE przez `send_text`: tamta ścieżka
        jest wspólna z Telegramem, gdzie formatowanie jest HTML-em, a
        Web Push HTML-a nie renderuje i pokazałby dosłowne znaczniki.
        """
        await self._send(
            push_payload.allegro_lokalnie_event(
                event_type=event.event_type,
                listing_title=event.opis,
                quantity=event.quantity,
                amount=event.amount,
                message_id=event.message_id,
                # Doręczenie i anulowanie niczego nie wymagają - rzeczy
                # skończone nie dzwonią. Zwrot ma osobny typ i dzwoni.
                silent=event.event_type == "order_status",
            )
        )

    async def notify_olx_event(self, event: OlxEvent) -> None:
        """
        Zdarzenie z OLX - katalog, pozycja „OLX".

        Treść budujemy z katalogu, a NIE przez `send_text`: tamta ścieżka
        jest wspólna z Telegramem, gdzie formatowanie jest HTML-em, a
        Web Push HTML-a nie renderuje i pokazałby dosłowne znaczniki.
        """
        await self._send(
            push_payload.olx_event(
                event_type=event.event_type,
                opis=event.opis,
                message_id=event.message_id,
            )
        )

    async def notify_new_dispute(self, notice: DisputeNotice) -> None:
        """Nowa dyskusja - katalog, pozycja „Nowa dyskusja"."""
        await self._send(
            push_payload.new_dispute(
                buyer_login=notice.buyer_login,
                reason=notice.reason,
                respond_by=notice.respond_by,
                issue_id=notice.issue_id,
            )
        )

    async def notify_sync_failed(self, channel: str, retry_in_minutes: int) -> None:
        """Kanał nie odpowiada - katalog, pozycja „Błąd synchronizacji"."""
        await self._send(
            push_payload.sync_failed(channel=channel, retry_in_minutes=retry_in_minutes)
        )

    async def notify_mailbox_unavailable(self, login_rejected: bool, retry_in_minutes: int) -> None:
        """Skrzynka nie działa - katalog, pozycja „Poczta nie działa"."""
        await self._send(
            push_payload.mailbox_unavailable(
                login_rejected=login_rejected, retry_in_minutes=retry_in_minutes
            )
        )

    async def send_text(self, text: str) -> None:
        """
        Dowolna wiadomość tekstowa (np. alert o błędzie z innej warstwy).

        Trafia do wątku `sync`, bo to jedyne miejsce w katalogu na
        komunikaty techniczne. Bez akcji „Wycisz" - alert, który da się
        wyciszyć jednym kliknięciem, przestaje być alertem.

        `strip_html` to SIATKA BEZPIECZEŃSTWA: ta ścieżka jest wspólna
        z Telegramem, gdzie treść bywa formatowana znacznikami HTML.
        Web Push HTML-a nie renderuje, więc bez tego oczyszczenia na
        ekranie blokady lądowały dosłowne `<b>` i `<code>` - to był
        zgłoszony błąd. Zdarzenia warte powiadomienia mają własne pozycje
        w katalogu; to zabezpiecza wszystko, co przyjdzie tędy w przyszłości.
        """
        await self._send(
            PushPayload(
                title="ORDLY",
                body=push_payload.strip_html(text),
                thread="sync",
                url="/settings",
                actions=[{"action": "open", "title": "Pokaż"}],
            )
        )

    async def send_test(self) -> PushDeliveryReport:
        """
        Testowe powiadomienie z przycisku w Ustawieniach telefonu.

        Różni się od `send_text` dwiema rzeczami:

        - **zwraca realny wynik wysyłki** - wcześniej endpoint odpowiadał
          „wysłano do N urządzeń", licząc wiersze w bazie, także martwe
          subskrypcje starego telefonu. Po zmianie telefonu użytkownik
          widział „wysłano do 1 urządzenia", a nic nie przychodziło;
        - **pomija godziny ciszy** - test o 22:30 przychodziłby bez dźwięku
          i wyglądałby na niedziałający, choć użytkownik sam o niego prosi.

        Treść pochodzi z katalogu (`test_notification`). Dawniej tytuł
        brzmiał "ORDLY", a treść "…z ORDLY" - razem z podpisem "from ORDLY",
        który Safari dokłada sam, nazwa padała trzy razy.
        """
        return await self._send(push_payload.test_notification(), respect_quiet_hours=False)

    async def _send(
        self,
        payload: PushPayload,
        *,
        respect_quiet_hours: bool = True,
        counts: AttentionCounts | None = None,
    ) -> PushDeliveryReport:
        """
        Wysyła jedno powiadomienie do wszystkich zapisanych subskrypcji.

        Godziny ciszy są nakładane TUTAJ, a nie w budowniczych treści -
        dzięki temu żadna ścieżka wysyłki nie może ich przypadkiem
        pominąć. Jedynym wyjątkiem jest test wywołany ręcznie
        (`send_test`).
        """
        if respect_quiet_hours and push_payload.is_quiet_hour(local_now().time()):
            payload = replace(payload, silent=True)

        # Plakietka na ikonie = suma "Wymaga uwagi" z ekranu Start, liczona
        # przy KAŻDYM powiadomieniu. Nie da się jej już ustawić "po swojemu"
        # w pojedynczym builderze - wcześniej każdy robił to inaczej.
        payload = replace(payload, badge=await self._badge(counts))
        return await self._deliver(payload)

    async def _deliver(self, payload: PushPayload) -> PushDeliveryReport:
        """
        Dostarcza GOTOWE powiadomienie (cisza i plakietka już nałożone)
        do wszystkich subskrypcji. Oddzielone od `_send`, żeby testy mogły
        sprawdzić samą decyzję - treść, dźwięk, plakietkę - bez bazy
        i bez serwerów push.
        """
        serialized = payload.to_json()
        outcomes: list[_SendOutcome] = []

        async with self._session_scope_factory() as session:
            repository = SqlitePushSubscriptionRepository(session)
            subscriptions = await repository.get_all()

            for subscription in subscriptions:
                outcomes.append(await self._send_one(repository, subscription, serialized))

        return PushDeliveryReport(
            subscriptions=len(subscriptions),
            delivered=outcomes.count("delivered"),
            expired=outcomes.count("expired"),
            failed=outcomes.count("failed"),
        )

    async def _badge(self, counts: AttentionCounts | None) -> int | None:
        """
        Liczba na ikonie. `None` = nie zmieniaj plakietki: gdy nie ma
        licznika albo policzenie się nie udało - lepiej zostawić starą
        liczbę niż pokazać zaniżoną.
        """
        if counts is None:
            if self._attention_counter is None:
                return None
            try:
                counts = await self._attention_counter()
            except Exception as exc:  # noqa: BLE001 - powiadomienie ma wyjść mimo to
                logger.warning("Plakietka push: nie udało się policzyć ({})", exc)
                return None
        return counts.badge

    async def _send_one(
        self,
        repository: SqlitePushSubscriptionRepository,
        subscription: PushSubscription,
        payload: str,
    ) -> _SendOutcome:
        """
        Wysyła powiadomienie do jednej subskrypcji.

        Kod 404/410 oznacza, że przeglądarka odrzuciła/wygasiła
        subskrypcję - usuwamy ją, żeby kolejne wysyłki jej nie próbowały.
        Inne błędy są logowane, ale nie przerywają wysyłki do reszty
        subskrybentów.
        """
        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
        }
        try:
            await asyncio.to_thread(
                webpush,
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=self._vapid_private_key,
                vapid_claims=dict(self._vapid_claims),
            )
        except WebPushException as exc:
            status_code = getattr(exc.response, "status_code", None)
            if status_code in _GONE_STATUS_CODES:
                logger.info(
                    "Subskrypcja Web Push wygasła (HTTP {}) - usuwam endpoint",
                    status_code,
                )
                await repository.delete_by_endpoint(subscription.endpoint)
                return "expired"
            logger.warning("Wysyłka Web Push nie powiodła się: {}", exc)
            return "failed"
        except Exception:
            logger.exception("Nieoczekiwany błąd wysyłki Web Push")
            return "failed"
        return "delivered"
