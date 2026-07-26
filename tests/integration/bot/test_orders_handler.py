"""
Testy integracyjne handlera /orders - weryfikują, że komenda Telegram
(bot ORDLY) poprawnie wywołuje serwis i formatuje odpowiedź, bez
łączenia się z prawdziwym Telegram API.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.bot.handlers.orders import handle_orders


class FakeContainer:
    """Minimalny fake kontenera zwracający zaprogramowany serwis zamówień."""

    def __init__(self, orders_service) -> None:
        self._orders_service = orders_service

    def orders_service(self, session) -> object:
        return self._orders_service


class FakeOrdersService:
    """Fake serwisu zwracający zaprogramowaną listę zamówień."""

    def __init__(self, orders) -> None:
        self._orders = orders

    async def get_recent_orders(self, limit: int):
        return self._orders[:limit]


class TestOrdersHandler:
    """Testy formatowania odpowiedzi komendy /orders."""

    @pytest.mark.asyncio
    async def test_wyswietla_liste_zamowien(self, sample_order):
        """Handler powinien wypisać każde zamówienie w odpowiedzi."""
        message = MagicMock()
        message.answer = AsyncMock()
        container = FakeContainer(FakeOrdersService([sample_order]))

        await handle_orders(message, container, session=None)

        message.answer.assert_awaited_once()
        sent_text = message.answer.call_args.args[0]
        assert sample_order.external_id in sent_text
        assert sample_order.buyer.login in sent_text

    @pytest.mark.asyncio
    async def test_informuje_o_braku_zamowien(self):
        """Handler powinien wyświetlić czytelny komunikat, gdy brak zamówień."""
        message = MagicMock()
        message.answer = AsyncMock()
        container = FakeContainer(FakeOrdersService([]))

        await handle_orders(message, container, session=None)

        message.answer.assert_awaited_once()
        sent_text = message.answer.call_args.args[0]
        assert "Brak zapisanych zamówień." in sent_text
