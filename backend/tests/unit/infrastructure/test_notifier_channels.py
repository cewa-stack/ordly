"""
Rozdział formatowania między kanałami powiadomień.

Zgłoszony błąd wziął się stąd, że JEDNA treść - sformatowana pod Telegram
(`<b>`, `<code>`) - szła do wszystkich kanałów naraz. Telegram HTML
renderuje, Web Push nie, więc na ekranie blokady lądowały dosłowne
znaczniki. Te testy pilnują obu stron tej granicy: że Telegram nadal
dostaje bogaty format i że push nie dostaje go nigdy.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.infrastructure.telegram.telegram_notifier import TelegramNotifier
from app.infrastructure.webpush import push_payload


class FakeBotZWiadomosciami:
    """Bot testowy zapamiętujący wysłane wiadomości zamiast wołać Telegram API."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.messages.append(text)


class TestTelegramZachowujeFormat:
    """
    Kryterium odbioru: „Telegram (bot) nadal wygląda tak jak dziś".
    Zmiana dotyczyła WYŁĄCZNIE kanału Web Push.
    """

    @pytest.mark.asyncio
    async def test_ostrzezenie_o_magazynie_ma_pogrubienie_i_komende(self):
        bot = FakeBotZWiadomosciami()
        notifier = TelegramNotifier(bot, admin_chat_id=1)  # type: ignore[arg-type]

        await notifier.notify_unmatched_products(
            "b2784ef0-a0c0-11f1", ["Butelki PET 30 ml", "Nakrętki DIN18"]
        )

        assert len(bot.messages) == 1
        text = bot.messages[0]
        assert "<b>Sprzedaż poza magazynem</b>" in text
        assert "<code>/stock link [oferta] [SKU] [ilość]</code>" in text
        assert "• Butelki PET 30 ml" in text
        assert "• Nakrętki DIN18" in text
        assert "b2784ef0-a0c0-11f1" in text

    @pytest.mark.asyncio
    async def test_nazwa_produktu_ze_znakiem_mniejszosci_jest_escapowana(self):
        """
        Bot wysyła z `parse_mode=HTML` - surowy `<` w nazwie produktu
        wywróciłby parsowanie po stronie Telegrama i wiadomość by nie
        doszła w ogóle.
        """
        bot = FakeBotZWiadomosciami()
        notifier = TelegramNotifier(bot, admin_chat_id=1)  # type: ignore[arg-type]

        await notifier.notify_unmatched_products("ref", ["Butelka <30 ml>"])

        text = bot.messages[0]
        assert "&lt;30 ml&gt;" in text
        assert "<30 ml>" not in text


class TestPushNigdyNieDostajeHtml:
    """
    Druga strona granicy: cokolwiek trafi do treści push, nie może
    zawierać nawiasów kątowych.
    """

    def test_katalog_nie_produkuje_znacznikow(self):
        payloads = [
            push_payload.new_order(
                marketplace="allegro",
                amount=Decimal("60.94"),
                currency="PLN",
                products=[(50, "Butelki PET 30 ml")],
                external_id="x",
            ),
            push_payload.many_new_orders(
                count=2,
                per_channel={"allegro": 1, "olx": 1},
                total_amount=Decimal("100.00"),
                currency="PLN",
            ),
            push_payload.low_stock(name="A", sku="S", stock=1, min_stock=10),
            push_payload.new_dispute(
                buyer_login="a", reason="niezgodny z opisem", respond_by=None, issue_id="i"
            ),
            push_payload.new_return(external_id="r", products_summary="A", reason="b"),
            push_payload.pending_packing(count=3, oldest_since="wczoraj"),
            push_payload.sync_failed(channel="allegro", retry_in_minutes=5),
            push_payload.wholesaler_confirmed(wholesaler_name="Pako", items_summary="A"),
            push_payload.unmatched_products(reference="r", product_names=["A"]),
            push_payload.allegro_lokalnie_event(
                event_type="new_order",
                listing_title="A",
                quantity=1,
                amount=None,
                message_id="<m@x>",
            ),
        ]

        for payload in payloads:
            assert "<" not in payload.title, payload.title
            assert "<" not in payload.body, payload.body

    def test_tresc_telegramowa_przepuszczona_wspolna_sciezka_traci_znaczniki(self):
        """
        Dokładnie ten tekst wychodził na iPhone'a przed naprawą - łącznie
        z dosłownym `<b>` i `<code>`.
        """
        telegramowy = (
            "⚠️ <b>Sprzedaż poza magazynem</b>\n"
            "Zamówienie b2784ef0 zawiera pozycje bez powiązania z magazynem.\n"
            "Użyj <code>/stock link</code>."
        )

        oczyszczony = push_payload.strip_html(telegramowy)

        assert "<" not in oczyszczony
        assert "Sprzedaż poza magazynem" in oczyszczony
