"""
Jedna reguła zapisu zmiany stanu magazynowego.

Sprzedaż, zwrot i korekta wsteczna mapowania zmieniają stan w ten sam
sposób: przycinają wynik do zera i zostawiają wpis w historii ruchów.
Trzymanie tego w jednym miejscu gwarantuje, że raport magazynowy widzi
wszystkie te zmiany jednakowo (`source`, `reference`).
"""

from __future__ import annotations

from dataclasses import replace

from loguru import logger

from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.inventory_movement import InventoryMovement
from app.domain.interfaces.inventory_repository import InventoryRepository
from app.utils.time import utc_now


async def apply_stock_change(
    inventory: InventoryRepository,
    sku: str,
    change: int,
    reason: str,
    source: str,
    reference: str | None,
) -> InventoryItem | None:
    """
    Zmienia stan jednego produktu i zapisuje ruch w historii.

    Stan nigdy nie spada poniżej zera - przy rozjeździe danych odejmowana
    jest maksymalna dostępna ilość (z ostrzeżeniem w logu), bo ujemny stan
    magazynowy nie opisuje niczego, co da się policzyć na półce.

    Returns:
        Zaktualizowany produkt lub None, gdy SKU nie istnieje w magazynie.
    """
    item = await inventory.get_by_sku(sku)
    if item is None:
        logger.warning("Składnik '{}' nie istnieje w magazynie - pomijam", sku)
        return None

    new_stock = item.stock + change
    if new_stock < 0:
        logger.warning(
            "Stan produktu '{}' spadłby poniżej zera ({} szt., zmiana {}) - przycinam do zera",
            item.sku,
            item.stock,
            change,
        )
        new_stock = 0
        change = new_stock - item.stock

    await inventory.set_stock(item.sku, new_stock)
    await inventory.record_movement(
        InventoryMovement(
            item_sku=item.sku,
            item_name=item.name,
            change=change,
            stock_after=new_stock,
            reason=reason,
            source=source,
            reference=reference,
            occurred_at=utc_now(),
        )
    )
    logger.info(
        "Magazyn: {} {}{} szt. -> stan {} ({})",
        item.sku,
        "+" if change >= 0 else "",
        change,
        new_stock,
        reason,
    )
    return replace(item, stock=new_stock)
