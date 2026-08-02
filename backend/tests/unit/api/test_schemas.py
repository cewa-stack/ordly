"""Testy jednostkowe mapowania schematów API - status magazynowy."""

from __future__ import annotations

from app.api.schemas import stock_item_out
from app.domain.entities.inventory_item import InventoryItem


def _item(stock: int, min_stock: int) -> InventoryItem:
    return InventoryItem(sku="SKU-1", name="Produkt testowy", stock=stock, min_stock=min_stock)


class TestStockItemOutStatus:
    """
    `StockItemOut.status` musi odzwierciedlać dokładnie to, co widzi
    użytkownik jako kolor odznaki w apkach (mobile/desktop) - patrz
    InventoryItem.status_emoji, z którym ta funkcja jest celowo
    zsynchronizowana.
    """

    def test_zero_stan_daje_critical(self):
        assert stock_item_out(_item(stock=0, min_stock=10)).status == "critical"

    def test_niezerowy_stan_na_lub_ponizej_minimum_daje_warning(self):
        assert stock_item_out(_item(stock=4, min_stock=10)).status == "warning"
        assert stock_item_out(_item(stock=10, min_stock=10)).status == "warning"

    def test_stan_powyzej_minimum_daje_ok(self):
        assert stock_item_out(_item(stock=200, min_stock=25)).status == "ok"
