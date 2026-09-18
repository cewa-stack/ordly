"""Encja domenowa pojedynczego ręcznego wpisu ilości przy ofercie."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class OfferStockMovement:
    """
    Wpis historii ilości - kto kiedy i na ile poprawił stan oferty.

    `change` jest None przy pierwszym wpisie dla danej oferty: nie było
    poprzedniej ilości, więc nie ma od czego liczyć różnicy.
    """

    change: int | None
    quantity_after: int
    reason: str
    occurred_at: datetime
