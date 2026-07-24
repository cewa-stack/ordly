"""Notifier rozgłaszający do wielu kanałów jednocześnie (fan-out)."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine, Sequence
from typing import Any

from loguru import logger

from app.domain.entities.order import Order
from app.domain.entities.order_return import OrderReturn
from app.domain.interfaces.notifier import Notifier
from app.shared.dto.reminder_dto import ShippingReminderData


class CompositeNotifier(Notifier):
    """
    Wysyła każde powiadomienie do wszystkich skonfigurowanych kanałów
    (dziś: Telegram + Web Push) równolegle.

    Kontrakt zgodności wstecznej z `event_subscriptions.py`: wywołujący
    kod interpretuje wyjątek z `notifier.notify_*()` jako "powiadomienie
    NIE dotarło" (np. nie oznacza zamówienia jako `notified`). Dlatego
    ten notifier rzuca wyjątek tylko, gdy WSZYSTKIE kanały zawiodły -
    jeśli chociaż jeden dostarczył wiadomość, użytkownik został
    powiadomiony i wywołujący kod ma to widzieć jako sukces.
    """

    def __init__(self, notifiers: Sequence[Notifier]) -> None:
        """
        Args:
            notifiers: Kanały powiadomień, w kolejności w jakiej mają
                zostać odpytane (wszystkie równolegle, nie sekwencyjnie).
        """
        self._notifiers = list(notifiers)

    async def _run_all(self, coros: Sequence[Coroutine[Any, Any, None]]) -> None:
        """Uruchamia wszystkie coroutine równolegle i ocenia wynik zbiorowo."""
        if not coros:
            return

        results = await asyncio.gather(*coros, return_exceptions=True)
        failures = [r for r in results if isinstance(r, BaseException)]

        if len(failures) == len(results):
            raise failures[-1]

        for failure in failures:
            logger.opt(exception=failure).warning(
                "Jeden z kanałów powiadomień zawiódł - inne mogły się powieść"
            )

    async def notify_new_order(self, order: Order) -> None:
        """Rozgłasza nowe zamówienie do wszystkich kanałów."""
        await self._run_all([n.notify_new_order(order) for n in self._notifiers])

    async def notify_order_cancelled(self, order: Order) -> None:
        """Rozgłasza anulowanie zamówienia do wszystkich kanałów."""
        await self._run_all([n.notify_order_cancelled(order) for n in self._notifiers])

    async def notify_order_return(self, order_return: OrderReturn) -> None:
        """Rozgłasza zwrot produktów do wszystkich kanałów."""
        await self._run_all(
            [n.notify_order_return(order_return) for n in self._notifiers]
        )

    async def notify_low_stock(
        self, name: str, sku: str, stock: int, min_stock: int
    ) -> None:
        """Rozgłasza ostrzeżenie o niskim stanie magazynowym do wszystkich kanałów."""
        await self._run_all(
            [
                n.notify_low_stock(name, sku, stock, min_stock)
                for n in self._notifiers
            ]
        )

    async def notify_shipping_reminder(self, data: ShippingReminderData) -> None:
        """Rozgłasza przypomnienie o wysyłce do wszystkich kanałów."""
        await self._run_all(
            [n.notify_shipping_reminder(data) for n in self._notifiers]
        )

    async def notify_active_orders(self, orders: list[Order]) -> None:
        """Rozgłasza listę aktualnych zamówień do wszystkich kanałów."""
        await self._run_all([n.notify_active_orders(orders) for n in self._notifiers])

    async def send_text(self, text: str) -> None:
        """Rozgłasza dowolny tekst do wszystkich kanałów."""
        await self._run_all([n.send_text(text) for n in self._notifiers])
