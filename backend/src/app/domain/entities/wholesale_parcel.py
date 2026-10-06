"""Paczka od hurtowni nadana przez InPost - jednorazowa informacja ([FEAT-MAIL])."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class WholesaleParcelNotice:
    """
    InPost potwierdził nadanie paczki od hurtowni do sklepu.

    Czysto informacyjne: ORDLY nie wiąże tej paczki z żadnym zamówieniem
    i nie zmienia na jej podstawie żadnego statusu.

    `message_id` (nagłówek Message-ID maila) jest kluczem deduplikacji -
    jeden mail daje najwyżej jeden alert.
    """

    message_id: str
    tracking_number: str
    wholesaler_name: str
    received_at: datetime
