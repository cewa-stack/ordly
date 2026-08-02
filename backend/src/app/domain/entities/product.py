"""Encja domenowa reprezentująca produkt w ramach zamówienia."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Product:
    """Pozycja (produkt) będąca częścią zamówienia."""

    external_id: str
    name: str
    quantity: int
    unit_price: Decimal

    @property
    def total_price(self) -> Decimal:
        """Zwraca łączną cenę tej pozycji (ilość * cena jednostkowa)."""
        return self.unit_price * self.quantity
