"""Fake implementacja Notifier - zapamiętuje wysłane powiadomienia zamiast Telegrama."""

from __future__ import annotations

from app.domain.entities.order import Order
from app.domain.entities.order_return import OrderReturn
from app.domain.interfaces.notifier import Notifier
from app.shared.dto.reminder_dto import ShippingReminderData


class FakeNotifier(Notifier):
    """Zapisuje wysłane powiadomienia w liście, do sprawdzenia w asercjach testu."""

    def __init__(self) -> None:
        self.sent_orders: list[Order] = []
        self.sent_cancellations: list[Order] = []
        self.sent_returns: list[OrderReturn] = []
        self.sent_texts: list[str] = []
        self.sent_low_stock: list[tuple[str, str, int, int]] = []
        self.sent_reminders: list[ShippingReminderData] = []
        self.sent_active_orders: list[list[Order]] = []

    async def notify_new_order(self, order: Order) -> None:
        self.sent_orders.append(order)

    async def notify_order_cancelled(self, order: Order) -> None:
        self.sent_cancellations.append(order)

    async def notify_order_return(self, order_return: OrderReturn) -> None:
        self.sent_returns.append(order_return)

    async def notify_low_stock(
        self, name: str, sku: str, stock: int, min_stock: int
    ) -> None:
        self.sent_low_stock.append((name, sku, stock, min_stock))

    async def notify_shipping_reminder(self, data: ShippingReminderData) -> None:
        self.sent_reminders.append(data)

    async def notify_active_orders(self, orders: list[Order]) -> None:
        self.sent_active_orders.append(list(orders))

    async def send_text(self, text: str) -> None:
        self.sent_texts.append(text)
