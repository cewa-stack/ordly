"""Implementacja Notifier wysyłająca powiadomienia przez Telegram (bot TOOM)."""

from __future__ import annotations

from aiogram import Bot, html
from loguru import logger

from app.domain.entities.order import Order
from app.domain.entities.order_return import OrderReturn
from app.domain.interfaces.notifier import Notifier
from app.shared.dto.reminder_dto import ShippingReminderData


class TelegramNotifier(Notifier):
    """Wysyła powiadomienia biznesowe na skonfigurowany chat administratora."""

    def __init__(self, bot: Bot, admin_chat_id: int) -> None:
        """
        Args:
            bot: Skonfigurowana instancja bota aiogram (TOOM).
            admin_chat_id: Chat ID, na który wysyłane są wszystkie powiadomienia.
        """
        self._bot = bot
        self._admin_chat_id = admin_chat_id

    async def notify_new_order(self, order: Order) -> None:
        """
        Wysyła sformatowane powiadomienie o nowym zamówieniu.

        Dane pochodzące z marketplace (numer, login, nazwy produktów)
        są escapowane - bot używa parse_mode=HTML, a znaki `<`, `>`
        i `&` w danych zewnętrznych powodowałyby błąd wysyłki.
        """
        text = (
            "📦 <b>NOWE ZAMÓWIENIE</b>\n\n"
            f"Numer: {html.quote(order.external_id)}\n"
            f"Kupujący: {html.quote(order.buyer.login)}\n"
            f"Kwota: {order.total_amount} {order.currency}\n"
            f"Produkty: {html.quote(order.products_summary)}\n"
            f"Data: {order.order_date.strftime('%Y-%m-%d %H:%M')}"
        )
        await self.send_text(text)

    async def notify_order_cancelled(self, order: Order) -> None:
        """
        Wysyła sformatowane powiadomienie o anulowaniu zamówienia.

        Dane z marketplace są escapowane z tego samego powodu,
        co w notify_new_order (parse_mode=HTML).
        """
        text = (
            "❌ <b>ZAMÓWIENIE ANULOWANE</b>\n\n"
            f"Numer: {html.quote(order.external_id)}\n"
            f"Kupujący: {html.quote(order.buyer.login)}\n"
            f"Kwota: {order.total_amount} {order.currency}\n"
            f"Produkty: {html.quote(order.products_summary)}\n"
            f"Data zamówienia: {order.order_date.strftime('%Y-%m-%d %H:%M')}"
        )
        await self.send_text(text)

    async def notify_order_return(self, order_return: OrderReturn) -> None:
        """
        Wysyła sformatowane powiadomienie o zwrocie produktów z zamówienia.

        Dane z marketplace są escapowane z tego samego powodu,
        co w notify_new_order (parse_mode=HTML).
        """
        text = (
            "↩️ <b>ZWROT PRODUKTÓW</b>\n\n"
            f"Zamówienie: {html.quote(order_return.order_external_id)}\n"
            f"Numer zwrotu: {html.quote(order_return.external_id)}\n"
            f"Kupujący: {html.quote(order_return.buyer_login)}\n"
            f"Produkty: {html.quote(order_return.products_summary)}\n"
            f"Status: {html.quote(order_return.status)}\n"
            f"Data zgłoszenia: {order_return.created_at.strftime('%Y-%m-%d %H:%M')}"
        )
        await self.send_text(text)

    async def notify_low_stock(
        self, name: str, sku: str, stock: int, min_stock: int
    ) -> None:
        """
        Wysyła ostrzeżenie o osiągnięciu minimalnego stanu magazynowego.

        Nazwa i SKU pochodzą z danych wprowadzonych przez użytkownika,
        więc są escapowane (parse_mode=HTML).
        """
        text = (
            "⚠️ <b>MAGAZYN - NISKI STAN</b>\n\n"
            f"Produkt: {html.quote(name)}\n"
            f"SKU: {html.quote(sku)}\n"
            f"Pozostało: {stock} szt. (minimum: {min_stock})\n\n"
            "Produkt dodano do listy zakupów.\n"
            "Rozważ zamówienie nowej dostawy."
        )
        await self.send_text(text)

    async def notify_shipping_reminder(self, data: ShippingReminderData) -> None:
        """
        Wysyła przypomnienie o zamówieniach wymagających dziś wysyłki.

        Numery zamówień pochodzą z marketplace, więc są escapowane
        (parse_mode=HTML).
        """
        listed = data.unshipped_orders[:20]
        lines = "\n".join(
            f"• Zamówienie {html.quote(order.external_id)}" for order in listed
        )
        more = ""
        if data.unshipped_count > len(listed):
            more = f"\n… oraz {data.unshipped_count - len(listed)} więcej"

        text = (
            "📦 <b>Dzisiejsze zamówienia wymagające wysyłki</b>\n\n"
            f"Dzisiaj wpłynęło: {data.orders_today} zamówień\n"
            f"Do wysłania pozostało: {data.unshipped_count}\n\n"
            f"Lista:\n{lines}{more}\n\n"
            "Przypomnienie:\n"
            "Spakuj zamówienia i wygeneruj etykiety przewozowe."
        )
        await self.send_text(text)

    async def notify_active_orders(self, orders: list[Order]) -> None:
        """
        Publikuje listę aktualnych zamówień po nocnym czyszczeniu czatu.

        Numery zamówień i loginy kupujących pochodzą z marketplace, więc
        są escapowane (parse_mode=HTML).
        """
        lines = "\n".join(
            f"• Zamówienie {html.quote(order.external_id)} — "
            f"{html.quote(order.buyer.login)}"
            for order in orders
        )
        text = f"📦 <b>Nowe zamówienia</b>\n\n{lines}"
        await self.send_text(text)

    async def send_text(self, text: str) -> None:
        """
        Wysyła dowolny tekst na chat administratora, z odpornością na błędy.

        Błąd wysyłki (np. brak internetu, Telegram niedostępny) jest
        logowany, ale nie rzucany dalej - zgodnie z wymaganiem
        odporności projektu.
        """
        try:
            await self._bot.send_message(chat_id=self._admin_chat_id, text=text)
        except Exception:
            logger.exception("Nie udało się wysłać wiadomości Telegram")
