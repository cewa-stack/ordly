"""Encja domenowa reprezentująca przesyłkę."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Shipment:
    """
    Przesyłka powiązana z zamówieniem.

    Status przesyłki jest pobierany wyłącznie na żądanie (komenda
    /tracking), nigdy automatycznie przez scheduler.
    """

    order_external_id: str
    carrier: str | None
    tracking_number: str | None
    status: str | None
    updated_at: datetime | None
