"""Implementacja Notifier wysyłająca powiadomienia przez Telegram (bot ORDLY)."""

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
            bot: Skonfigurowana instancja bota aiogram (ORDLY).
            admin_chat_id: Chat ID, na który wysyłane są wszystkie powiadomienia.
        """
        self._bot = bot
        self._admin_chat_id = admin_chat_id

    async def notify_new_order(self, order: Order) -> None:
        """
        Wysyła sformatowane powiadomienie o nowym zamówieniu.

        Dane pochodzące z marketplace (numer, login, nazwy produktów)
        są escapowane - bot używa parse_mode=HTML, a znaki `<`, `>`
        i `&` w danych zewnętrznych powodowałyby błąd wysyłki. Numer
        zamówienia jest w <code> (monospace) - ta sama konwencja co
        "numery/SKU zawsze mono" w apkach mobilnej i desktopowej.
        """
        text = (
            "🆕 <b>Nowe zamówienie</b>\n"
            f"<code>#{html.quote(order.external_id)}</code> · {html.quote(order.marketplace)}\n\n"
            f"👤 {html.quote(order.buyer.login)}\n"
            f"💰 <b>{order.total_amount} {order.currency}</b>\n"
            f"🛍️ {html.quote(order.products_summary)}\n"
            f"🕐 {order.order_date.strftime('%d.%m.%Y %H:%M')}"
        )
        await self.send_text(text)

    async def notify_order_cancelled(self, order: Order) -> None:
        """
        Wysyła sformatowane powiadomienie o anulowaniu zamówienia.

        Dane z marketplace są escapowane z tego samego powodu,
        co w notify_new_order (parse_mode=HTML).
        """
        text = (
            "❌ <b>Zamówienie anulowane</b>\n"
            f"<code>#{html.quote(order.external_id)}</code> · {html.quote(order.marketplace)}\n\n"
            f"👤 {html.quote(order.buyer.login)}\n"
            f"💰 {order.total_amount} {order.currency}\n"
            f"🛍️ {html.quote(order.products_summary)}\n"
            f"🕐 Zamówione: {order.order_date.strftime('%d.%m.%Y %H:%M')}"
        )
        await self.send_text(text)

    async def notify_order_return(self, order_return: OrderReturn) -> None:
        """
        Wysyła sformatowane powiadomienie o zwrocie produktów z zamówienia.

        Dane z marketplace są escapowane z tego samego powodu,
        co w notify_new_order (parse_mode=HTML).
        """
        text = (
            "↩️ <b>Zwrot produktów</b>\n"
            f"<code>#{html.quote(order_return.external_id)}</code> "
            f"· zamówienie #{html.quote(order_return.order_external_id)}\n\n"
            f"👤 {html.quote(order_return.buyer_login)}\n"
            f"🛍️ {html.quote(order_return.products_summary)}\n"
            f"📋 Status: {html.quote(order_return.status)}\n"
            f"🕐 Zgłoszono: {order_return.created_at.strftime('%d.%m.%Y %H:%M')}"
        )
        await self.send_text(text)

    async def notify_low_stock(self, name: str, sku: str, stock: int, min_stock: int) -> None:
        """
        Wysyła ostrzeżenie o osiągnięciu minimalnego stanu magazynowego.

        Nazwa i SKU pochodzą z danych wprowadzonych przez użytkownika,
        więc są escapowane (parse_mode=HTML).
        """
        text = (
            "⚠️ <b>Niski stan magazynowy</b>\n"
            f"{html.quote(name)} · <code>{html.quote(sku)}</code>\n\n"
            f"📉 Zostało: <b>{stock} szt.</b> (minimum: {min_stock})\n\n"
            "Dodano do listy zakupów — rozważ zamówienie nowej dostawy."
        )
        await self.send_text(text)

    async def notify_shipping_reminder(self, data: ShippingReminderData) -> None:
        """
        Wysyła wieczorne przypomnienie o zamówieniach czekających na
        spakowanie (status NEW), niezależnie od tego, kiedy wpłynęły.

        Numery i loginy pochodzą z marketplace, więc są escapowane
        (parse_mode=HTML).
        """
        listed = data.new_orders[:20]
        lines = "\n".join(
            f"▫️ #{html.quote(order.external_id)} — {html.quote(order.buyer.login)} "
            f"· {order.total_amount} {order.currency}"
            for order in listed
        )
        more = (
            f"\n<i>…oraz {data.new_count - len(listed)} więcej</i>"
            if data.new_count > len(listed)
            else ""
        )

        text = (
            "🌙 <b>Wieczorne przypomnienie</b>\n"
            f"Masz jeszcze <b>{data.new_count}</b> nietkniętych zamówień do spakowania:\n\n"
            f"{lines}{more}\n\n"
            "Zanim skończysz dzień — spakuj i nadaj, co się da. 📦"
        )
        await self.send_text(text)

    async def notify_active_orders(self, orders: list[Order]) -> None:
        """
        Publikuje listę aktualnych zamówień po nocnym czyszczeniu czatu.

        Numery zamówień i loginy kupujących pochodzą z marketplace, więc
        są escapowane (parse_mode=HTML).
        """
        lines = "\n".join(
            f"▫️ <code>#{html.quote(order.external_id)}</code> — {html.quote(order.buyer.login)}"
            for order in orders
        )
        text = f"📦 <b>Aktualne zamówienia</b> ({len(orders)})\n\n{lines}"
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
