"""Encja domenowa reprezentująca pojedynczą zmianę stanu magazynowego."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

MOVEMENT_SOURCE_MANUAL = "manual"
MOVEMENT_SOURCE_ORDER = "order"
MOVEMENT_SOURCE_RETURN = "return"
MOVEMENT_SOURCE_CANCELLATION = "cancellation"


@dataclass(frozen=True, slots=True)
class InventoryMovement:
    """
    Wpis historii magazynu - każda zmiana stanu (ręczna lub automatyczna)
    jest utrwalana jako osobny, niemutowalny ruch magazynowy.

    `reference` wskazuje źródłowy dokument (np. numer zamówienia Allegro),
    dzięki czemu historię można powiązać z konkretną operacją biznesową.
    """

    item_sku: str
    item_name: str
    change: int
    stock_after: int
    reason: str
    source: str
    reference: str | None
    occurred_at: datetime
