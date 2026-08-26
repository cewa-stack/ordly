"""
Kaskadowanie zmian stanu na podprodukty (1:1, tylko dla sprzedaży).

Butelka 10 ml sprzedaje się zawsze z nakrętką i kroplomierzem, więc gdy
sprzedaż zdejmie 100 butelek, tyle samo musi zejść z nakrętek
i kroplomierzy - niezależnie od tego, przez którą ofertę i który serwis
poszła transakcja.

Wywoływane WYŁĄCZNIE przez `StockSyncService` (sprzedaż, anulowanie,
zwrot). Ręczne korekty w `InventoryService` nigdy tego nie wołają - to
świadoma decyzja, nie przeoczenie: inwentaryzację i dostawę liczy się
i wpisuje osobno dla każdego SKU, bo do magazynu przyjeżdżają osobne
kartony butelek i osobne kartony nakrętek.
"""

from __future__ import annotations

from collections.abc import Collection

from app.domain.entities.inventory_item import InventoryItem
from app.domain.interfaces.inventory_repository import InventoryRepository
from app.services.stock_ledger import apply_stock_change


async def cascade_to_sub_items(
    inventory: InventoryRepository,
    parent_sku: str,
    change: int,
    reason: str,
    source: str,
    reference: str,
    skip_skus: Collection[str] = (),
) -> list[InventoryItem]:
    """
    Aplikuje dokładnie tę samą zmianę (1:1) do wszystkich podproduktów.

    Args:
        inventory: Repozytorium magazynu.
        parent_sku: SKU produktu głównego, którego stan właśnie się zmienił.
        change: Zmiana stanu produktu głównego - ta sama liczba idzie
            do każdego podproduktu, bo proporcja jest zawsze 1:1.
        reason, source, reference: Opis ruchu przepisany z dokumentu
            źródłowego, żeby historia podproduktu wskazywała to samo
            zamówienie co historia produktu głównego.
        skip_skus: SKU pominięte w kaskadzie. Służy jednej rzeczy:
            recepturze oferty, która wymienia i produkt główny,
            i jego podprodukt osobno (stary sposób z trzema składnikami).
            Bez tego takie sprzedaż odjęłaby nakrętkę dwa razy - raz
            jako składnik receptury, raz przez kaskadę.

    Returns:
        Zaktualizowane podprodukty - do sprawdzenia progu niskiego stanu
        przez wywołującego.
    """
    pominiete = set(skip_skus)
    updated: list[InventoryItem] = []
    for sub_item in await inventory.get_sub_items(parent_sku):
        if sub_item.sku in pominiete:
            continue
        result = await apply_stock_change(
            inventory=inventory,
            sku=sub_item.sku,
            change=change,
            reason=f"{reason} (podprodukt: {parent_sku})",
            source=source,
            reference=reference,
        )
        if result is not None:
            updated.append(result)
    return updated
