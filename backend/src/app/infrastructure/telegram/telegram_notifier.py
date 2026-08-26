"""Implementacja Notifier wysyłająca powiadomienia przez Telegram (bot ORDLY)."""

from __future__ import annotations

from aiogram import Bot, html
from loguru import logger

from app.domain.entities.allegro_lokalnie_event import AllegroLokalnieEvent
from app.domain.entities.dispute_notice import DisputeNotice
from app.domain.entities.order import Order
from app.domain.entities.order_return import OrderReturn
from app.domain.interfaces.notifier import Notifier
from app.shared.dto.reminder_dto import ShippingReminderData

#: Nagłówki zdarzeń z Allegro Lokalnie - emoji + pogrubiona nazwa, tak
#: jak reszta powiadomień bota. Telegram renderuje HTML, więc pogrubienie
#: zostaje (w przeciwieństwie do Web Push, gdzie katalog daje czysty tekst).
_ALLEGRO_LOKALNIE_HEADLINES = {
    "new_order": "🛒 <b>Nowe zamówienie — Allegro Lokalnie</b>",
    "order_status": "🔄 <b>Zmiana zamówienia — Allegro Lokalnie</b>",
    "new_message": "💬 <b>Nowa wiadomość — Allegro Lokalnie</b>",
    "interest": "👀 <b>Pytanie o ogłoszenie — Allegro Lokalnie</b>",
    "unknown": "📩 <b>Powiadomienie z Allegro Lokalnie</b>",
}


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

    async def notify_allegro_lokalnie(self, event: AllegroLokalnieEvent) -> None:
        """
        Zdarzenie z Allegro Lokalnie odczytane z powiadomienia e-mail.

        Temat i fragment treści pochodzą z maila od obcego nadawcy, więc
        idą przez `html.quote` - inaczej znak `<` w tytule ogłoszenia
        wywróciłby parsowanie HTML po stronie Telegrama i wiadomość by
        nie doszła.
        """
        headline = _ALLEGRO_LOKALNIE_HEADLINES.get(
            event.event_type, _ALLEGRO_LOKALNIE_HEADLINES["unknown"]
        )
        ile = f"{event.quantity}× " if event.quantity else ""
        wiersze = [headline, f"🛍️ {ile}{html.quote(event.opis)}"]
        if event.amount is not None:
            wiersze.append(f"💰 <b>{event.amount:.2f} zł</b>")
        if event.buyer:
            wiersze.append(f"👤 {html.quote(event.buyer)}")
        text = "\n".join(wiersze) + (
            "\n\n<i>Allegro Lokalnie nie ma API - tym zamówieniem zarządzasz "
            "na stronie serwisu. ORDLY tylko o nim mówi.</i>"
        )
        await self.send_text(text)

    async def notify_new_dispute(self, notice: DisputeNotice) -> None:
        """
        Kupujący rozpoczął dyskusję.

        Login, powód i nazwa oferty pochodzą z maila od Allegro, więc idą
        przez `html.quote` - bot wysyła z `parse_mode=HTML` i surowy `<`
        w nazwie oferty wywróciłby parsowanie.
        """
        wiersze = [f"💬 <b>Nowa dyskusja</b> — {html.quote(notice.buyer_login)}"]
        if notice.reason:
            wiersze.append(f"❗ {html.quote(notice.reason)}")
        if notice.offer_name:
            wiersze.append(f"🛍️ {html.quote(notice.offer_name)}")
        if notice.order_external_id:
            wiersze.append(f"<code>#{html.quote(notice.order_external_id)}</code>")
        if notice.respond_by is not None:
            wiersze.append(
                f"⏳ Odpowiedz do <b>{notice.respond_by.strftime('%d.%m.%Y %H:%M')}</b>, "
                "inaczej Allegro włączy się do rozmowy."
            )
        await self.send_text("\n".join(wiersze))

    async def notify_unmatched_products(
        self, reference: str, product_names: list[str]
    ) -> None:
        """
        Sprzedaż bez powiązania z magazynem - format BEZ ZMIAN względem
        tego, co bot wysyłał dotąd.

        Telegram renderuje HTML, więc pogrubienie i `<code>` z komendą do
        skopiowania zostają - to one czynią tę wiadomość użyteczną na
        desktopie. Zmiana dotyczyła wyłącznie kanału Web Push, gdzie ten
        sam tekst wychodził jako surowe znaczniki.
        """
        products = "\n".join(f"• {html.quote(name)}" for name in product_names)
        text = (
            "⚠️ <b>Sprzedaż poza magazynem</b>\n"
            f"Zamówienie {html.quote(reference)} zawiera pozycje bez powiązania "
            "z magazynem, więc stany się nie zmieniły:\n"
            f"{products}\n\n"
            "Przypisz składniki w Magazyn → Powiązania ofert "
            "(albo <code>/stock link [oferta] [SKU] [ilość]</code>)."
        )
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
