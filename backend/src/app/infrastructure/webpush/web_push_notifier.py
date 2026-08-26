"""
Implementacja Notifier wysyłająca powiadomienia przez Web Push (RFC 8030)
do ORDLY Mobile uruchomionego jako PWA (drugi kanał obok Telegrama,
przeznaczony głównie na iPhone'a, gdzie natywny push wymaga płatnego
konta Apple Developer).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import replace
from decimal import Decimal

from loguru import logger
from pywebpush import WebPushException, webpush
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.allegro_lokalnie_event import AllegroLokalnieEvent
from app.domain.entities.dispute_notice import DisputeNotice
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
from app.shared.dto.reminder_dto import ShippingReminderData
from app.utils.time import local_now

_GONE_STATUS_CODES = (404, 410)


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
    ) -> None:
        """
        Args:
            session_scope_factory: `Container.session_scope` - Notifier
                jest tworzony bez sesji (tak jak TelegramNotifier), więc
                sam otwiera sobie krótkotrwałą sesję na czas jednej wysyłki.
            vapid_private_key: Klucz prywatny VAPID (base64url, format RAW).
            vapid_claim_email: Adres z prefiksem `mailto:` wymagany przez
                specyfikację VAPID jako identyfikator nadawcy.
        """
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
        Anulowane zamówienie.

        Katalog z sekcji 03 nie ma osobnej pozycji dla anulowania, ale
        to zdarzenie zdejmuje pracę z listy - idzie więc jako ciche
        powiadomienie w wątku zamówień, żeby lista w telefonie się
        zgadzała bez budzenia użytkownika.
        """
        await self._send(
            PushPayload(
                title="Zamówienie anulowane",
                body=f"{order.buyer.login} — {order.products_summary}.",
                thread="orders",
                url=f"/orders/{order.external_id}",
                silent=True,
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

    async def notify_low_stock(self, name: str, sku: str, stock: int, min_stock: int) -> None:
        """Niski stan - katalog, pozycja „Niski stan"."""
        await self._send(
            push_payload.low_stock(name=name, sku=sku, stock=stock, min_stock=min_stock)
        )

    async def notify_shipping_reminder(self, data: ShippingReminderData) -> None:
        """Zaległe pakowanie - katalog, pozycja „Zaległe pakowanie"."""
        if data.new_count == 0:
            return
        oldest = min(order.order_date for order in data.new_orders)
        await self._send(
            push_payload.pending_packing(
                count=data.new_count,
                oldest_since=oldest.strftime("%H:%M"),
                badge=data.new_count,
            )
        )

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
                badge=1,
            )
        )

    async def notify_unmatched_products(
        self, reference: str, product_names: list[str]
    ) -> None:
        """Sprzedaż poza magazynem - katalog, pozycja „Sprzedaż poza magazynem"."""
        await self._send(
            push_payload.unmatched_products(reference=reference, product_names=product_names)
        )

    async def notify_sync_failed(self, channel: str, retry_in_minutes: int) -> None:
        """Kanał nie odpowiada - katalog, pozycja „Błąd synchronizacji"."""
        await self._send(
            push_payload.sync_failed(channel=channel, retry_in_minutes=retry_in_minutes)
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

    async def _send(self, payload: PushPayload) -> None:
        """
        Wysyła jedno powiadomienie do wszystkich zapisanych subskrypcji.

        Godziny ciszy są nakładane TUTAJ, a nie w budowniczych treści -
        dzięki temu żadna ścieżka wysyłki nie może ich przypadkiem
        pominąć.
        """
        if push_payload.is_quiet_hour(local_now().time()):
            payload = replace(payload, silent=True)

        serialized = payload.to_json()

        async with self._session_scope_factory() as session:
            repository = SqlitePushSubscriptionRepository(session)
            subscriptions = await repository.get_all()

            if not subscriptions:
                return

            for subscription in subscriptions:
                await self._send_one(repository, subscription, serialized)

    async def _send_one(
        self,
        repository: SqlitePushSubscriptionRepository,
        subscription: PushSubscription,
        payload: str,
    ) -> None:
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
            else:
                logger.warning("Wysyłka Web Push nie powiodła się: {}", exc)
        except Exception:
            logger.exception("Nieoczekiwany błąd wysyłki Web Push")
