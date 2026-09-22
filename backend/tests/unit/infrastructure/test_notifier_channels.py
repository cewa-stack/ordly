"""
Rozdział formatowania między kanałami powiadomień.

Zgłoszony błąd wziął się stąd, że JEDNA treść - sformatowana pod Telegram
(`<b>`, `<code>`) - szła do wszystkich kanałów naraz. Telegram HTML
renderuje, Web Push nie, więc na ekranie blokady lądowały dosłowne
znaczniki. Te testy pilnują obu stron tej granicy: że Telegram nadal
dostaje bogaty format i że push nie dostaje go nigdy.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from app.domain.entities.olx_event import OlxEvent
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

    @staticmethod
    async def _wyslij_olx(listing_title: str) -> str:
        bot = FakeBotZWiadomosciami()
        notifier = TelegramNotifier(bot, admin_chat_id=1)  # type: ignore[arg-type]

        await notifier.notify_olx_event(
            OlxEvent(
                message_id="<olx-1@olx.pl>",
                event_type="new_order",
                subject="Wiadomości dotyczące ogłoszeń",
                snippet="Płatność została dokonana",
                received_at=datetime(2026, 9, 13, 10, 0),
                listing_title=listing_title,
            )
        )

        assert len(bot.messages) == 1
        return bot.messages[0]

    @pytest.mark.asyncio
    async def test_sprzedaz_z_olx_ma_pogrubienie_i_wyjasnienie(self):
        text = await self._wyslij_olx("Butelki PET 30 ml")

        assert "<b>Sprzedano — OLX</b>" in text
        assert "<b>Nie ma tego w zamówieniach</b>" in text
        assert "<i>" in text
        assert "Butelki PET 30 ml" in text

    @pytest.mark.asyncio
    async def test_nazwa_ogloszenia_ze_znakiem_mniejszosci_jest_escapowana(self):
        """
        Bot wysyła z `parse_mode=HTML` - surowy `<` w tytule ogłoszenia
        wywróciłby parsowanie po stronie Telegrama i wiadomość by nie
        doszła w ogóle. Realne tytuły z OLX bywają pełne interpunkcji.
        """
        text = await self._wyslij_olx("Butelka <30 ml>")

        assert "&lt;30 ml&gt;" in text
        assert "Butelka <30 ml>" not in text


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
            push_payload.new_dispute(
                buyer_login="a", reason="niezgodny z opisem", respond_by=None, issue_id="i"
            ),
            push_payload.new_return(external_id="r", products_summary="A", reason="b"),
            push_payload.morning_brief(
                pending_count=3, oldest_local=None, now_local=datetime(2026, 9, 22, 9, 0)
            ),
            push_payload.test_notification(),
            push_payload.sync_failed(channel="allegro", retry_in_minutes=5),
            push_payload.wholesaler_confirmed(wholesaler_name="Pako", items_summary="A"),
            push_payload.allegro_lokalnie_event(
                event_type="new_order",
                listing_title="A",
                quantity=1,
                amount=None,
                message_id="<m@x>",
            ),
            push_payload.olx_event(event_type="unknown", opis="A", message_id="<m@olx.pl>"),
            push_payload.olx_event(event_type="new_order", opis="A", message_id="<m@olx.pl>"),
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
