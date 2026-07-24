"""
Implementacja Notifier wysyłająca powiadomienia przez Web Push (RFC 8030)
do TOOM Mobile uruchomionego jako PWA (drugi kanał obok Telegrama,
przeznaczony głównie na iPhone'a, gdzie natywny push wymaga płatnego
konta Apple Developer).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from loguru import logger
from pywebpush import WebPushException, webpush
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.order import Order
from app.domain.entities.order_return import OrderReturn
from app.domain.entities.push_subscription import PushSubscription
from app.domain.interfaces.notifier import Notifier
from app.repositories.sqlite_push_subscription_repository import (
    SqlitePushSubscriptionRepository,
)
from app.shared.dto.reminder_dto import ShippingReminderData

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

    async def notify_new_order(self, order: Order) -> None:
        """Wysyła powiadomienie o nowym zamówieniu."""
        await self._broadcast(
            "Nowe zamówienie",
            f"{order.external_id} — {order.buyer.login} — "
            f"{order.total_amount} {order.currency}",
        )

    async def notify_order_cancelled(self, order: Order) -> None:
        """Wysyła powiadomienie o anulowaniu zamówienia."""
        await self._broadcast(
            "Zamówienie anulowane",
            f"{order.external_id} — {order.buyer.login}",
        )

    async def notify_order_return(self, order_return: OrderReturn) -> None:
        """Wysyła powiadomienie o zwrocie produktów z zamówienia."""
        await self._broadcast(
            "Zwrot produktów",
            f"Zamówienie {order_return.order_external_id} — "
            f"{order_return.buyer_login} — {order_return.status}",
        )

    async def notify_low_stock(
        self, name: str, sku: str, stock: int, min_stock: int
    ) -> None:
        """Wysyła ostrzeżenie o osiągnięciu minimalnego stanu magazynowego."""
        await self._broadcast(
            "Magazyn — niski stan",
            f"{name} ({sku}) — zostało {stock} szt. (minimum: {min_stock})",
        )

    async def notify_shipping_reminder(self, data: ShippingReminderData) -> None:
        """Wysyła przypomnienie o zamówieniach wymagających dziś wysyłki."""
        await self._broadcast(
            "Przypomnienie o wysyłce",
            f"Do wysłania dziś: {data.unshipped_count} z {data.orders_today} zamówień",
        )

    async def notify_active_orders(self, orders: list[Order]) -> None:
        """Powiadamia o liście aktualnych zamówień po nocnym czyszczeniu czatu."""
        if not orders:
            return
        await self._broadcast(
            "Aktualne zamówienia",
            f"{len(orders)} zamówień wymaga dziś obsługi",
        )

    async def send_text(self, text: str) -> None:
        """Wysyła dowolną wiadomość tekstową (np. alert o błędzie)."""
        await self._broadcast("TOOM", text)

    async def _broadcast(self, title: str, body: str) -> None:
        """Wysyła jedno powiadomienie do wszystkich zapisanych subskrypcji."""
        payload = json.dumps({"title": title, "body": body})

        async with self._session_scope_factory() as session:
            repository = SqlitePushSubscriptionRepository(session)
            subscriptions = await repository.get_all()

            if not subscriptions:
                return

            for subscription in subscriptions:
                await self._send_one(repository, subscription, payload)

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
