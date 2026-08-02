"""Encja domenowa opisująca składnik oferty marketplace (mapowanie na magazyn)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OfferComponent:
    """
    Jeden składnik oferty marketplace w przeliczeniu na produkt magazynowy.

    Zwykła oferta ma jeden składnik (quantity=1). Zestaw (np. Starter Kit)
    ma wiele składników - po sprzedaży jednej sztuki oferty magazyn
    odejmuje `quantity` sztuk każdego składnika.
    """

    sku: str
    quantity: int
