"""Encja domenowa reprezentująca fakturę/dokument sprzedaży."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Invoice:
    """
    Dokument sprzedaży powiązany z zamówieniem.

    Zdefiniowana zgodnie z wymaganiami architektury domenowej -
    przyszłe pluginy (np. integracja z systemem księgowym) będą
    operować na tej samej encji.
    """

    order_external_id: str
    invoice_number: str | None
    total_amount: Decimal
    currency: str
    issued: bool
