"""Encja domenowa reprezentująca przesyłkę."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Shipment:
    """
    Przesyłka powiązana z zamówieniem.

    Pobierana zarówno na żądanie (komenda /tracking), jak i automatycznie
    przez check_waybills_job. `status` to wewnętrzna etykieta ORDLY, nie
    wartość z Allegro - endpoint GET .../shipments w ogóle nie zwraca
    statusu, więc mapper ustawia "NADANA", gdy wpis istnieje, albo
    "PRZYGOTOWYWANA", gdy lista przesyłek jest pusta (patrz mapper.py).
    """

    order_external_id: str
    carrier: str | None
    tracking_number: str | None
    status: str | None
    updated_at: datetime | None
