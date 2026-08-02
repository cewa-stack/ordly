"""Testy jednostkowe encji InventoryItem - status_emoji i is_low_stock."""

from __future__ import annotations

from app.domain.entities.inventory_item import InventoryItem


def _item(stock: int, min_stock: int) -> InventoryItem:
    return InventoryItem(sku="SKU-1", name="Produkt testowy", stock=stock, min_stock=min_stock)


class TestStatusEmoji:
    """Testy klasyfikacji stanu magazynowego (🔴/🟡/🟢)."""

    def test_zero_stock_jest_zawsze_czerwony(self):
        """Stan 0 to zawsze brak, niezależnie od skonfigurowanego minimum."""
        assert _item(stock=0, min_stock=0).status_emoji == "🔴"
        assert _item(stock=0, min_stock=10).status_emoji == "🔴"

    def test_stan_ponizej_lub_rowny_minimum_ale_niezerowy_jest_zolty(self):
        """Stan > 0, ale na/poniżej minimum - "zamów wkrótce", nie "brak"."""
        assert _item(stock=4, min_stock=10).status_emoji == "🟡"
        assert _item(stock=10, min_stock=10).status_emoji == "🟡"

    def test_stan_powyzej_minimum_jest_zielony(self):
        """Stan wyraźnie powyżej minimum to OK."""
        assert _item(stock=42, min_stock=0).status_emoji == "🟢"
        assert _item(stock=200, min_stock=25).status_emoji == "🟢"
        assert _item(stock=11, min_stock=10).status_emoji == "🟢"

    def test_brak_skonfigurowanego_minimum_nigdy_nie_daje_zoltego(self):
        """min_stock == 0 oznacza brak monitorowania progu - zawsze OK poza zerem."""
        assert _item(stock=1, min_stock=0).status_emoji == "🟢"


class TestIsLowStock:
    """is_low_stock to osobne pojęcie (lista zakupów/powiadomienia) - nie zmieniamy go tutaj."""

    def test_is_low_stock_wymaga_dodatniego_minimum(self):
        assert _item(stock=0, min_stock=0).is_low_stock is False

    def test_is_low_stock_true_na_lub_ponizej_minimum(self):
        assert _item(stock=4, min_stock=10).is_low_stock is True
        assert _item(stock=10, min_stock=10).is_low_stock is True

    def test_is_low_stock_false_powyzej_minimum(self):
        assert _item(stock=11, min_stock=10).is_low_stock is False
